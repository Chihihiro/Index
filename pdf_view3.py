# -*- coding: utf-8 -*-
import sys
import pandas as pd
import re
import os
import pymysql
import time
import subprocess
import datetime
import shutil
import smtplib
import logging
from sqlalchemy import create_engine
from win32com import client
from email.header import Header
from email.mime.text import MIMEText
from email.utils import parseaddr, formataddr
from email.mime.multipart import MIMEMultipart
from xml.etree import ElementTree as ET
from os.path import getsize
from threading import Timer
import win32com.client

engine = create_engine(
    "mysql+pymysql://{}:{}@{}:{}/{}".format('root', 'Chihiro123+', '10.3.2.25', 3306, 'base', ),
    connect_args={"charset": "utf8"}, echo=True, )


class mv_file:
    """
    type_file : 'all' 是全部, 可以指定各种格式pdf,csv,xlsx
    """

    def __init__(self, old_path, new_path, type_file='all'):
        self.old_path = old_path
        self.new_path = new_path
        self.files = []
        self.type_file = type_file

    def read_files(self):
        if self.type_file == 'all':
            self.files = os.listdir(self.old_path)
        else:
            files = os.listdir(self.old_path)
            self.files = [i for i in files if i[-len(self.type_file):] == self.type_file]
        return self.files

    def move_files(self):
        if not os.path.exists(self.new_path):
            os.makedirs(self.new_path)  # 创建路径
        files_list = self.read_files()
        for i in files_list:
            srcfile = self.old_path + '\\' + i
            dstfile = self.new_path + '\\' + i
            shutil.move(srcfile, dstfile)
            print("move %s -> %s" % (srcfile, dstfile))

    def copy_files(self):
        if not os.path.exists(self.new_path):
            os.makedirs(self.new_path)  # 创建路径
        files_list = self.read_files()
        for i in files_list:
            srcfile = self.old_path + '\\' + i
            dstfile = self.new_path + '\\' + i
            shutil.copy(srcfile, dstfile)
            print("copy %s -> %s" % (srcfile, dstfile))

    def del_files(self):
        files_list = self.read_files()
        for i in files_list:
            srcfile = self.old_path + '\\' + i
            os.remove(srcfile)
            print("del %s " % srcfile)


class to_email:

    def __init__(self, to_addre):
        self.to_addre = to_addre

    def format_addr(self, s):
        name, addr = parseaddr(s)
        return formataddr((Header(name, 'utf-8').encode(), addr))

    def course(self):
        # 输入Email地址和口令:
        from_addr = '632207812@qq.com'
        password = 'aphstjyszatqbecc'
        # 输入收件人地址:
        # to_addr = '632207812@qq.com'
        # 输入SMTP服务器地址:
        smtp_server = 'smtp.qq.com'
        msg = MIMEMultipart()
        msg.attach(MIMEText('pdf解析完成请查收', 'plain', 'utf-8'))
        # msg = MIMEText('hello, send by Python...', 'plain', 'utf-8')#正文
        msg['From'] = self.format_addr('黄义超 <%s>' % from_addr)  # 发件人 不该就成为邮箱地址
        msg['To'] = self.format_addr('收件人 <%s>' % self.to_addre)  # 收件人
        msg['Subject'] = Header('pdf解析的报告', 'utf-8').encode()  # 标题

        path = os.getcwd()
        a = mv_file(old_path=path, new_path=path, type_file='.csv')
        b = a.read_files()

        lu = path + '\\' + b[0]
        att1 = MIMEText(open(lu, 'rb').read(), 'base64', 'utf-8')
        att1["Content-Type"] = 'application/octet-stream'
        att1["Content-Disposition"] = 'attachment; filename="{}"'.format(b[0])
        msg.attach(att1)
        server = smtplib.SMTP(smtp_server, 25)
        server.set_debuglevel(1)
        server.login(from_addr, password)
        server.sendmail(from_addr, [self.to_addre], msg.as_string())
        server.quit()


def check_exsit(process_name):
    """
    关闭指定进程
    :param process_name:  xxx.exe
    :return:
    """
    WMI = win32com.client.GetObject('winmgmts:')
    processCodeCov = WMI.ExecQuery('select * from Win32_Process where Name="%s"' % process_name)
    if len(processCodeCov) > 0:
        return 1
    else:
        return 0


def sql_cols(df, usage="sql"):
    cols = tuple(df.columns)
    if usage == "sql":
        cols_str = str(cols).replace("'", "`")
        if len(df.columns) == 1:
            cols_str = cols_str[:-2] + ")"  # to process dataframe with only one column
        return cols_str
    elif usage == "format":
        base = "'%%(%s)s'" % cols[0]
        for col in cols[1:]:
            base += ", '%%(%s)s'" % col
        return base
    elif usage == "values":
        base = "%s=VALUES(%s)" % (cols[0], cols[0])
        for col in cols[1:]:
            base += ", `%s`=VALUES(`%s`)" % (col, col)
        return base


def to_sql(tb_name, conn, dataframe, type="update", chunksize=2000, debug=False):
    """
    Dummy of pandas.to_sql, support "REPLACE INTO ..." and "INSERT ... ON DUPLICATE KEY UPDATE (keys) VALUES (values)"
    SQL statement.

    Args:
        tb_name: str
            Table to insert get_data;
        conn:
            DBAPI Instance
        dataframe: pandas.DataFrame
            Dataframe instance
        type: str, optional {"update", "replace", "ignore"}, default "update"
            Specified the way to update get_data. If "update", then `conn` will execute "INSERT ... ON DUPLICATE UPDATE ..."
            SQL statement, else if "replace" chosen, then "REPLACE ..." SQL statement will be executed; else if "ignore" chosen,
            then "INSERT IGNORE ..." will be excuted;
        chunksize: int
            Size of records to be inserted each time;
        **kwargs:

    Returns:
        None
    """

    df = dataframe.copy(deep=False)
    df = df.fillna("None")
    df = df.applymap(lambda x: re.sub('([\'\"\\\])', '\\\\\g<1>', str(x)))
    cols_str = sql_cols(df)
    sqls = []
    for i in range(0, len(df), chunksize):
        # print("chunk-{no}, size-{size}".format(no=str(i/chunksize), size=chunksize))
        df_tmp = df[i: i + chunksize]

        if type == "replace":
            sql_base = "REPLACE INTO `{tb_name}` {cols}".format(
                tb_name=tb_name,
                cols=cols_str
            )

        elif type == "update":
            sql_base = "INSERT INTO `{tb_name}` {cols}".format(
                tb_name=tb_name,
                cols=cols_str
            )
            sql_update = "ON DUPLICATE KEY UPDATE {0}".format(
                sql_cols(df_tmp, "values")
            )

        elif type == "ignore":
            sql_base = "INSERT IGNORE INTO `{tb_name}` {cols}".format(
                tb_name=tb_name,
                cols=cols_str
            )

        sql_val = sql_cols(df_tmp, "format")
        vals = tuple([sql_val % x for x in df_tmp.to_dict("records")])
        sql_vals = "VALUES ({x})".format(x=vals[0])
        for i in range(1, len(vals)):
            sql_vals += ", ({x})".format(x=vals[i])
        sql_vals = sql_vals.replace("'None'", "NULL")

        sql_main = sql_base + sql_vals
        if type == "update":
            sql_main += sql_update

        if sys.version_info.major == 2:
            sql_main = sql_main.replace("u`", "`")
        if sys.version_info.major == 3:
            sql_main = sql_main.replace("%", "%%")

        if debug is False:
            try:
                conn.execute(sql_main)
            except pymysql.err.InternalError as e:
                print("ENCOUNTERING ERROR: {e}, RETRYING".format(e=e))
                time.sleep(10)
                conn.execute(sql_main)
        else:
            sqls.append(sql_main)
    if debug:
        return sqls


def now_time(a=0):
    now = datetime.datetime.now()
    delta = datetime.timedelta(days=a)
    n_days = now + delta
    print(n_days.strftime('%Y-%m-%d %H:%M:%S'))
    f = n_days.strftime('%Y-%m-%d')
    return f


def now_time2(a=0):
    now = datetime.datetime.now()
    delta = datetime.timedelta(minutes=a)
    n_days = now + delta
    print(n_days.strftime('%Y-%m-%d %H:%M:%S'))
    f = n_days.strftime('%Y%m%d%H%M')
    return f


def strQ2B(ustring):
    """全角转半角"""
    rstring = ""
    for uchar in ustring:
        inside_code = ord(uchar)
        if inside_code == 12288:  # 全角空格直接转换
            inside_code = 32
        elif (inside_code >= 65281 and inside_code <= 65374):  # 全角字符（除空格）根据关系转化
            inside_code -= 65248

        rstring = rstring + chr(inside_code)
    return rstring


def doc2pdf(doc_name, pdf_name):
    """
    :word文件转pdf
    :param doc_name word文件名称
    :param pdf_name 转换后pdf文件名称
    """
    try:
        word = client.DispatchEx("Word.Application")
        if os.path.exists(pdf_name):
            os.remove(pdf_name)
        worddoc = word.Documents.Open(doc_name, ReadOnly=1)
        worddoc.SaveAs(pdf_name, FileFormat=17)
        worddoc.Close()
        # worddoc.quit()
        word.Close()
        word.quit()
        os.system('taskkill /f /im WINWORD.EXE')
        return pdf_name
    except:
        # worddoc.Close()
        return 1


def all_doc2pdf(path):
    files = os.listdir(path)
    docs = []
    for i in files:
        if '.doc' in i:
            docs.append(i)
        else:
            pass
    for doc in docs:
        in_name = path + doc
        out_name = path + doc[:-3] + 'pdf'
        try:
            doc2pdf(in_name, out_name)
            print(doc + 'successful')
        except BaseException as e:
            print(e)
        else:
            pass


def len_pdf(all_files=r'\\vm-zdhjg64\resource\pdf\港股其他 (月報表等)'):
    lls = []
    dfp = pd.read_sql("select pdf_name from pdf_match", engine)
    opdf = dfp['pdf_name'].values.tolist()
    for dirpath, dirnames, filenames in os.walk(all_files):
        for filename in filenames:
            if filename in opdf:
                pass
            else:
                cc = dirpath + '\\' + filename
                if cc[-4:] in ['.pdf', '.doc']:
                    lls.append(cc)
    return lls


class pdf_analysis:
    def __init__(self):
        self.self_path = os.getcwd()
        self.xml_path = os.getcwd() + "\\1start\\xml"
        self.logname = now_time2()

    def read_xml(self, path):
        """读取xml"""
        books = []
        try:
            print(path)
            tree = ET.parse(path)
            root = tree.getroot()
            childs = root.getchildren()
            self.console_out(type='debug', error="开始解析：" + os.path.basename(path)[4:-4])

            for child0 in childs:
                for child00 in child0.getchildren():
                    bb = child00.text
                    books.append("喵厸" + re.sub("s/|\|", "甲鸭", strQ2B(bb)) + "喵厸")
        except BaseException as e:
            self.console_out(type='error', error=e)
        return books

    def clean(self, txt, zhenze):
        """正则提取加清洗"""
        try:
            num = re.sub("", "", re.search(zhenze, txt).group(1))
        except BaseException:
            num = ''
        else:
            pass
        return num

    def relist(self, list, ss):
        ll = []
        for i in list:
            a = self.clean(ss, "{}".format(i))
            print(a)
            if type(a) is str and len(a) >= 1:
                ll.append(a)
        if len(ll) >= 1:
            print('采集合集:', ll)
            # ll.sort(key=lambda i: len(i), reverse=True)
            return ll
        else:
            return None

    def getdirsize(self, name):
        size = getsize(name)
        print(size)  # 输出文件的大小
        return size

    def only_num(self, x):
        if type(x) is str:
            try:
                t = re.sub(",", "", x)
                print(t)
                txt = re.findall('[0-9]+', t)
                print(txt)
                num = [float(x) for x in txt if x != '']
            except BaseException:
                return None
            return num
        else:
            try:
                x = '喵'.join(x)
                t = re.sub(",", "", x)
                print(t)
                txt = re.findall('[0-9]+', t)
                print(txt)
                num = [float(x) for x in txt if x != '']
            except BaseException:
                return None
            return num

    def process(self, all_files):
        vlist = []

        lls = []
        # all_files = r'C:\Users\qinxd\Desktop\pp'
        for dirpath, dirnames, filenames in os.walk(all_files):
            for filename in filenames:
                cc = dirpath + '\\' + filename
                if cc[-4:] in ['.xml']:
                    lls.append(cc)

        for path in lls:

            name = os.path.basename(path)
            try:
                size = self.getdirsize(path)

                if size < 2000:
                    psize = '文件可能是图片需要查看'
                    v = None
                    vlist.append([name, v, psize])
                else:
                    psize = 'pass'
                    Z1 = self.read_xml(path)
                    df = pd.DataFrame(Z1)
                    v = ['上月底結存', '本月增加/(減少)', '增加/(減少)', '本月底結存', '本月增加', '本月底结存',
                         "增加/\(減少\)(.+?)本月優先股增加"]

                    df = df.reset_index(level=0)
                    df.columns = ["SUM", "A"]

                    def zero(strs):
                        s = 0
                        for i in v:
                            if i in strs:
                                s += 1
                        return s

                    df["B"] = df["A"].apply(lambda x: zero(x) if type(x) is str else 0)
                    df["C"] = (df["B"].shift(1) + df["B"].shift(-1) + df["B"])
                    llmax = list(set(df["C"].tolist()))
                    llmax = [int(i) for i in llmax if i >= 2]
                    df['D'] = list(map(lambda x, y: x if y in llmax else None, df['SUM'], df['C']))
                    p = list(set(df["D"].tolist()))
                    p = [int(i) for i in p if type(i) is float and i > 2]

                    """取坐标公司基本情况"""
                    size = 2
                    ps = []
                    p1 = []
                    for i in range(len(p)):
                        if i == (len(p) - 1):
                            p1.append(p[i])
                            ps.append(p1)
                        else:
                            if (p[i + 1] - p[i]) < size:
                                p1.append(p[i])
                            else:
                                p1.append(p[i])
                                new = p1.copy()
                                ps.append(new)
                                p1.clear()

                    maxandmin = [[min(i), max(i)] for i in ps]

                    wen = []
                    for i in range(len(maxandmin)):
                        df1 = df.iloc[maxandmin[i][0]:maxandmin[i][1], [1]]
                        t1 = df1["A"].tolist()
                        wen1 = ''.join(t1)
                        wen.append(wen1)

                    ff = ["本月增加/\(減少\)(.+?)本月底結存", "本月增加/\(減少\)(.+?)喵厸",
                          "增加/\(減少\)(.+?)本月底", "增加/\(減少\)(.+?)喵厸", "本月普通股增加/\(減少\)(.+?)本月優先股增加"]
                    caowen = []
                    for txt in wen:
                        # print(txt)
                        # s = clean(txt,"本月增加(.+?)本月底結存")
                        w = self.relist(ff, txt)
                        caowen.append(w)

                    nums = []
                    for i in caowen:
                        nb = self.only_num(i)
                        if type(nb) is list:
                            for yy in nb:
                                nums.append(yy)

                    nums = list(set(nums))
                    v = [str(i) for i in nums if i > 100]

                    wnums = ",".join(v)

                    if len(wnums) >= 1:
                        psize = '有数据请查看'

                    if wnums == []:
                        wnums = None

                    name = os.path.basename(path)
                    vlist.append([name, wnums, psize])
            except BaseException as e:
                print('文件打开失败')
                self.console_out(type='error', error=e)
                vlist.append([name, None, '无法解析请手动查看'])
        return vlist

    def console_out(self, type, error):
        ''''' Output log to file and console '''
        # Define a Handler and set a format which output to file
        logging.basicConfig(
            level=logging.DEBUG,  # 定义输出到文件的log级别，大于此级别的都被输出
            format='%(asctime)s  %(filename)s : %(levelname)s  %(message)s',  # 定义输出log的格式
            datefmt='%Y-%m-%d %A %H:%M:%S',  # 时间
            filename=os.getcwd() + '\\log\\{}.log'.format(self.logname),  # log文件名
            filemode='w')  # 写入模式“w”或“a”
        # Define a Handler and set a format which output to console
        console = logging.StreamHandler()  # 定义console handler
        console.setLevel(logging.INFO)  # 定义该handler级别
        formatter = logging.Formatter('%(asctime)s  %(filename)s : %(levelname)s  %(message)s')  # 定义该handler格式
        console.setFormatter(formatter)
        # Create an instance
        logging.getLogger().addHandler(console)  # 实例化添加handler
        # Print information              # 输出日志级别
        if type == 'debug':
            logging.debug('logger debug message: %s' % error)
        if type == 'message':
            logging.info('logger info message: %s' % error)
        if type == 'warning':
            logging.warning('logger warning message: %s' % error)
        if type == 'error':
            logging.error('logger error message: %s' % error)
        if type == 'critical':
            logging.critical('logger critical message: %s' % error)

    def course(self):
        print('start')
        all_files = r'\\vm-zdhjg64\resource\pdf\港股其他 (月報表等)'
        lls = []
        sql_look = "select pdf_name from pdf_match"
        dfp = pd.read_sql(sql_look, engine)
        opdf = dfp['pdf_name'].values.tolist()
        for dirpath, dirnames, filenames in os.walk(all_files):
            for filename in filenames:
                if filename in opdf:
                    pass
                else:
                    cc = dirpath + '\\' + filename
                    if cc[-4:] in ['.pdf', '.doc']:
                        lls.append(cc)
        print('新的pdf有' + str(len(lls)))
        if len(lls) > 0:
            pdfaddress = self.self_path + '\\1start\\xml\\pdfs\\'

            for ll in lls:
                shutil.copy(ll, pdfaddress)  # 复制文件到1star/xml/pdfs

            print('开始解析word')

            """word转pdf"""
            all_doc2pdf(path=pdfaddress)
            print('doc 转 pdf 成功')

            os.chdir(self.xml_path)
            # """cd 到文件夹运行PDF转xml"""
            subprocess.Popen(r'exec.bat -d "pdfs pdfs"')
            time.sleep(10 + len(lls) / 10)
            """等待pdf转xml解析结束"""
            os.chdir(self.self_path)

            """
            迁移存放pdf文件，存放旧的csv文件↓
            """
            csv_path = self.self_path + '\\存放旧csv\\'
            csv = mv_file(self.self_path + '\\', csv_path, type_file='.csv')
            csv.move_files()
            """上面是迁移csv"""
            """pdf信息入库"""
            pp = self.self_path + '\\1start\\xml\\pdfs\\'
            files = os.listdir(pp)
            """
            读取数据库里面已经解析的pdf
            """
            df_pdfs = pd.read_sql("select pdf_name from pdf_match", engine)
            pl = df_pdfs['pdf_name'].values.tolist()
            ma = [i for i in files if i not in pl]
            data = pd.DataFrame(ma, columns=['pdf_name'])

            """需要等待xml解析完成"""
            nbtime = 0
            for i, e in enumerate(range(len(lls))):
                print(i)
                nn = check_exsit('java.exe')
                time.sleep(5)
                nbtime += 5
                if nbtime == 15 + len(lls):
                    print('超过时间直接解析')
                    self.console_out(type='error', error='java解析超时')
                    break
                if nn < 1:
                    print('解析完成')
                    break

            rpath = self.self_path + '\\1start\\xml'
            result = self.process(rpath)
            dataframe = pd.DataFrame(result)
            dataframe.columns = ['文件名字', '解析结果', '解析状况']
            dataframe['文件名字'] = dataframe['文件名字'].apply(lambda x: x[4:-4])
            now = '\\' + now_time2() + '.csv'
            dataframe.to_csv(self.self_path + now, encoding='utf_8_sig')
            print('解析PDF成功')

            """
            传入邮箱
            """
            if len(lls) > 0:
                e = to_email('hkstock@gildata.com')
                e.course()
                # e1 = to_email('632207812@qq.com')
                # e1.course()

            to_sql('pdf_match', engine, data, type='update')  # 解析成功发送email成功然后入库

            try:
                a = mv_file(pdfaddress, pdfaddress, type_file='all')
                a.del_files()
            except BaseException as e:
                self.console_out(type='error', error=e)
            dd = mv_file(old_path=self.xml_path,
                         new_path=self.xml_path, type_file='.xml')
            dd.del_files()
        else:
            self.console_out(type='debug', error='本次没有文件解析')

    def main(self):
        self.course()
        self.console_out(type='debug', error='解析完毕无报错')

    def one(self, path):
        all = [path]
        g = self.process(all)
        return g


if __name__ == '__main__':
    """取消注释运行解析"""
    work = pdf_analysis()
    work.main()

"""上面程序主体下面是定时任务"""


def main():
    work = pdf_analysis()
    work.main()


def now_num(a=0):
    now = datetime.datetime.now()
    delta = datetime.timedelta(minutes=a)
    n_days = now + delta
    print(n_days.strftime('%Y-%m-%d %H:%M:%S'))
    f = n_days.strftime('%H')
    i = int(f)
    return i


def work():
    """定时任务每小时解析一次"""
    time = now_num()
    num = len(len_pdf())
    print(num)
    if 22 > time >= 6 and num > 50:
        main()
        print('开始任务')
        t = Timer(1 * 60 * 60, work)
        t.start()
    elif time == 23:
        # if num == 0:
        #     t = Timer(1 * 60 * 60, work)
        #     t.start()
        #     pass
        # else:
        #     main()
        #     t = Timer(1*60*60, work)
        #     t.start()
        if num == 23:
            pass
        else:
            main()

    else:
        print("数量不够不解析")
        t = Timer(1 * 60 * 60, work)
        t.start()


if __name__ == "__main__":
    work()
