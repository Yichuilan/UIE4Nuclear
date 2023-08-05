from flask import Flask, render_template, request,jsonify
from flask import Flask, send_file
import openpyxl
import csv
import chardet
from paddlenlp import Taskflow
import pandas as pd
schema={'组件': ['存在','包含'],'原因': ['导致'],'解决方案': ['解决'],"故障":[]}#'./re_pretrained/best'
ie = Taskflow(task='information_extraction', schema=schema,task_path='./UIE')
app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False
app.config['JSONIFY_MIMETYPE'] = "application/json;charset=utf-8"

class MyReq:
    def __init__(self):
        self.form={}

def process_e_r(out_data,js,entity,relation,con):
    if entity not in js[0]:
        return out_data
    temp_dict={'故障':[],entity:[]}
    for i in js[0][entity]:
        e1=i['text']
        if 'relations' in i:
            if relation in i['relations']:
                for e2 in i['relations'][relation]:
                    temp_dict['故障'].append(e2['text'])
                    temp_dict[entity].append(e1)
    if out_data is None:
        out_data=pd.DataFrame(temp_dict)
    else:
        temp_data=pd.DataFrame(temp_dict)
        if con!=0:
            out_data = pd.merge(out_data, temp_data, on=['故障',entity], how='outer')
        else:
            out_data = pd.merge(out_data, temp_data, on='故障', how='outer')
    return out_data

################
#用set代替，存储所有实体及关系
def get_e_r(req):
    all = {"e": {"组件": set(), "原因": set(), "解决方案": set(), "故障": set()},
           "r": {"存在": set(), "包含": set(), "导致": set(), "解决": set()}}
    out_data=None#out_data是pd数据格式
    l = len(req.form)
    for i in range(l):
        # 在这里执行对文本的处理操作
        num = i + 1
        x = ie(req.form.get('ptext' + str(num)))
        out_data=process_e_r(out_data, x, '组件','存在', i)
        out_data=process_e_r(out_data, x, '原因','导致', i)
        out_data=process_e_r(out_data, x, '解决方案','解决', i)
        for entity in x[0]:
            for e_item in x[0][entity]:
                all['e'][entity].add(e_item['text'])
                if 'relations' in e_item:
                    for relation in e_item['relations']:
                        for r_item in e_item['relations'][relation]:
                            all['r'][relation].add((e_item['text'],r_item['text']))
    return all,out_data

def get_mi(res):
    d={}
    r_l=[]
    for entity in res['e']:
        for item in res['e'][entity]:
            if item not in d:
                d[item]=entity
            elif item in d:
                d[item]=d[item]+'+'+entity
    for relation in res['r']:
        for item in res['r'][relation]:
            if item[0] not in d:
                d[item[0]]="其他"
            if item[1] not in d:
                d[item[1]]="其他"
            r_l.append((item[0],item[1],relation))
    return d,r_l

#根据实体类型，节点有四种颜色，同时也有未识别出的实体是另一种颜色（常见于关系中的目标对象）
#关系有四种颜色
@app.route('/')
def home():
    return render_template('src/Login.html')
@app.route('/login', methods=['POST'])
def login():
    ##登录逻辑
    return render_template('SearchBox.html',data={},dict={},relation={})

@app.route('/process', methods=['POST','GET'])
def process():
    response,out_data =get_e_r(request)
    map_index,r_index=get_mi(response)
    #将set()转化为None
    for key in response:
        for er in response[key]:
            if len(response[key][er])==0:
                response[key][er]={}

    #out_csv的处理部分
    column_names = out_data.columns.tolist()
    for m in ("组件", "故障", "解决方案", "原因"):
        if m not in column_names:
            out_data = out_data.assign(**{m: None})
    out_data = out_data.drop_duplicates()
    desired_order = ["组件", "故障", "原因", "解决方案"]
    out_data = out_data.reindex(columns=desired_order)
    out_data.to_excel('output.xlsx', index=False)
    return render_template('SearchBox.html',data=response,dict=map_index,relation=r_index)


@app.route('/upload', methods=['POST'])
def upload():
    temp1=request
    if 'file' not in request.files:
        return render_template('SearchBox.html', data={}, dict={}, relation={})
    file = request.files['file']
    if file.filename == '':
        return render_template('SearchBox.html', data={}, dict={}, relation={})
    req = MyReq()
    if file:
        # 处理上传的文件，这里可以根据需求进行文件的保存或处理
        # 例如保存文件到本地，或者将文件内容读取并处理
        file.save('upload/uploaded_file.xlsx')  # 这里将文件保存在当前目录下的uploaded_file.csv文件中
        with open('upload/uploaded_file.xlsx', 'rb') as csvfile:
            content = csvfile.read()
            detected_encoding = chardet.detect(content)['encoding']
        # 打开上传的xlsx文件
        wb = openpyxl.load_workbook('upload/uploaded_file.xlsx')
        sheet = wb.active
        tn=1
        for row in sheet.iter_rows(values_only=True):
            # row是一个列表，包含CSV文件的每一行数据
            # 在这里可以对每一行数据进行处理或保存等操作
            req.form['ptext'+str(tn)]=row[0]
            tn+=1
    response, out_data = get_e_r(req)
    map_index, r_index = get_mi(response)
    # 将set()转化为None
    for key in response:
        for er in response[key]:
            if len(response[key][er]) == 0:
                response[key][er] = {}
    # out_csv的处理部分
    column_names = out_data.columns.tolist()
    for m in ("组件", "故障", "解决方案", "原因"):
        if m not in column_names:
            out_data = out_data.assign(**{m: None})
    out_data = out_data.drop_duplicates()
    desired_order = ["组件", "故障", "原因", "解决方案"]
    out_data = out_data.reindex(columns=desired_order)
    out_data.to_excel('output.xlsx', index=False)
    return render_template('SearchBox.html', data=response, dict=map_index, relation=r_index)


@app.route('/download')
def download_file():
    path = 'output.xlsx' # 替换成本地a.csv的文件路径
    return send_file(path, as_attachment=True)

if __name__ == '__main__':
    app.run()

