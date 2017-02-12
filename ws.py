#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author: wushuiyong
# @Created Time : 日  1/ 1 23:43:12 2017
# @Description:
import tornado.ioloop
import tornado.web
import tornado.websocket
import json
import os
from StringIO import StringIO

import cel
import os, datetime
from fabric.api import run, env, local, cd, execute, sudo
from fabric import context_managers, colors

version = datetime.datetime.now().strftime('%Y%m%d%H%M%s')
project_name = ''
dir_codebase = '/Users/wushuiyong/workspace/meolu/data/codebase'
dir_release  = '/home/wushuiyong/walle/release'
dir_webroot  = '/home/wushuiyong/walle/webroot'
env.host_string = 'localhost'

class Index(tornado.web.RequestHandler):
    def get(self):
        self.render('say.html')

# 然后再改改, 安排每个连接者给其它连接者打个招呼.

class SocketHandler(tornado.websocket.WebSocketHandler):


    clients = set()

    @staticmethod
    def send_to_all(message):
        for c in SocketHandler.clients:
            c.write_message(json.dumps(message))

    @staticmethod
    def send(message):
        for c in SocketHandler.clients:
            c.write_message(json.dumps(message))

    def open(self):
        self.write_message(json.dumps({
            'type': 'sys',
            'message': 'Welcome to WebSocket',
        }))
        SocketHandler.send_to_all({
            'type': 'sys',
            'message': str(id(self)) + ' has joined',
        })
        SocketHandler.clients.add(self)

    def on_close(self):
        SocketHandler.clients.remove(self)
        SocketHandler.send_to_all({
            'type': 'sys',
            'message': str(id(self)) + ' has left',
        })


    def on_message(self, message):
        '''
        output format:
        [localhost] running: whoami && pwd
        wushuiyong
        /Users/wushuiyong


        :param message:
        :return:
        '''
        result = run('whoami')
        SocketHandler.send({'type': 'user', 'id': id(self), 'message': result,})
        result = run('python --version')
        SocketHandler.send({'type': 'user', 'id': id(self), 'message': result,})
        result = run('git --version')
        SocketHandler.send({'type': 'user', 'id': id(self), 'message': result,})
        async_result = cel.add.delay(message)
        result = async_result.get()
        stdout = StringIO()
        stderr = StringIO()
        context_managers.show('running', 'stdout', 'stderr')

        result = run('python --version')
        SocketHandler.send({'type': 'user', 'id': id(self), 'message': result.stdout,})
        result = run('git --version')
        SocketHandler.send({'type': 'user', 'id': id(self), 'message': result.stdout,})

        ret = run('whoami && pwd', combine_stderr=True, stdout=stdout, stderr=stderr)
        print(colors.green(ret))
        print(colors.red(stderr))
        print(colors.green(stdout))

        # result += ret
        print result
        # walle_deploy()

        # out_file = '/tmp/ws_01'
        # cmd = '%s > %s' % (message, out_file)
        # done = os.system(cmd)
        # stdOut = open(out_file)
        SocketHandler.send_to_all({
            'type': 'user',
            'id': id(self),
            'message': result,
        })
# class MainHandler(tornado.web.RequestHandler):
#     def get(self):
#         self.write("Hello, world")

def make_app():
    return tornado.web.Application([
        (r"/", Index),
        (r"/aso", SocketHandler),
    ])

# ===================== fabric ================

def prev_deploy():
    '''
    1.代码检出前要做的基础工作
    - 检查 当前用户
    - 检查 python 版本
    - 检查 git 版本
    - 检查 目录是否存在

    :return:
    '''


    run('whoami')
    run('python --version')
    run('git --version')
    run('mkdir -p %s' % (dir_codebase))
    pass

def deploy():
    '''
    2.检出代码

    :param project_name:
    :return:
    '''

    gitUri = 'git@gitlab.renrenche.com:marketing_center/wow.git'
    # 如果项目底下有 .git 目录则认为项目完整,可以直接检出代码
    if (os.path.exists(dir_codebase + '/.git')):
        with cd(dir_codebase):
            run('pwd && git pull')
    else:
        # 否则当作新项目检出完整代码
        with cd(dir_codebase):
            run('pwd && git clone %s .' % (gitUri))
    pass

def post_deploy():
    '''
    3.检出代码后要做的任务
    :return:
    '''
    pass

def prev_release():
    '''
    4.部署代码到目标机器前做的任务
    - 检查 webroot 父目录是否存在
    :return:
    '''
    execute(pre_release_webroot)
    pass

def pre_release_webroot():
    run('mkdir -p %s' % (dir_webroot))
    run('mkdir -p %s' % (dir_release))

def release():
    '''
    5.部署代码到目标机器做的任务
    - 打包代码 local
    - scp local => remote
    - 解压 remote
    :return:
    '''
    with cd(os.path.dirname(dir_codebase)):
        run('tar zcvf tar.tgz %s' % (project_name))
        for target_server in env.hosts:
            run('scp tar.tgz %s:%s/tar.tgz' % (target_server, dir_release))

        execute(release_untar)
    pass

def release_untar():
    '''
    解压版本包
    :return:
    '''
    with cd(dir_release):
        run('tar zxvf tar.tgz')

def post_release():
    '''
    6.部署代码到目标机器后要做的任务
    - 切换软链
    - 重启 nginx
    :return:
    '''

    execute(post_release_service)

    pass

def post_release_service():
    with cd(dir_webroot):
        run('ln -s %s %s/%s.%s.tmp' % (dir_release, dir_webroot, project_name, version))
        run('mv -fT %s.%s.tmp %s' % (project_name, version, project_name))
        sudo('nginx -s reload')

def walle_deploy():

    global dir_codebase, dir_release, dir_webroot, project_name
    # 定义项目名称
    project_name = 'wow'
    dir_codebase = '%s/%s' % (dir_codebase, project_name)
    dir_release  = '%s/%s' % (dir_release, project_name)


    # 定义远程机器
    env.hosts = ['172.16.0.231', '172.16.0.177']
    env.user  = 'wushuiyong'
    # target_server = ['127.0.0.1']

    # prev_deploy
    prev_deploy()

    # deploy
    deploy()

    # post_deploy
    post_deploy()

    # prev_release
    prev_release()

    # release
    release()

    # post_release
    post_release()

    pass

if __name__ == "__main__":
    app = make_app()
    app.listen(8888)
    tornado.ioloop.IOLoop.current().start()
