#!/usr/bin/env python

import json
import sys
import os
import time
from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
from subprocess import call


def get_full_name(url):
    [owner, name] = url.split('/')[-2:]
    owner = owner.split(':')[-1]  # ssh
    if name[-4:] == '.git':
        name = name[:-4]
    return '%s/%s' % (owner, name)


class GitAutoDeploy(BaseHTTPRequestHandler):

    CONFIG_FILEPATH = './GitAutoDeploy.conf.json'
    LOG_FILE = "log.txt"
    config = None
    quiet = False
    daemon = False

    @classmethod
    def getConfig(cls):
        if not cls.config:
            if os.path.isfile(cls.CONFIG_FILEPATH):
                try:
                    configfile = open(cls.CONFIG_FILEPATH)
                    configString = configfile.read()
                    configfile.close()
                    cls.config = json.loads(configString)
                except:
                    cls.log('Could not load config json file: ' +
                            cls.CONFIG_FILEPATH)

                for repository in cls.config['repositories']:
                    if not cls.checkPathWithUrl(repository['path'], repository['url'], repository['branch']):
                        sys.exit('Directory  is not a Git repository')
                        break

            elif not cls.quiet:  # try user input
                cls.config = cls.setConfig()

        return cls.config

    def do_POST(self):
        event = self.headers.getheader('X-Github-Event')
        self.log(event + " received")
        if event == 'ping':
            self.respond(204)
        elif event != 'push':
            self.respond(304)
        else:
            self.respond(204)
            repositories = self.parseRequest()
            self.log('Remote repository:' + repositories['url'])
            paths = self.getMatchingPaths(repositories['full_name'])
            for path in paths:
                self.deploy(path)

    def parseRequest(self):
        length = int(self.headers.getheader('content-length'))
        body = self.rfile.read(length)
        payload = json.loads(body)
        self.branch = payload['ref']
        return payload['repository']

    def getMatchingPaths(self, full_name):
        res = []
        config = self.getConfig()
        for repository in config['repositories']:
            if(get_full_name(repository['url']) == full_name):
                res.append(repository['path'])
        return res

    def respond(self, code):
        self.send_response(code)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()

    def deploy(self, path):
        config = self.getConfig()
        for repository in config['repositories']:
            if(repository['path'] == path):
                if 'branch' in repository:
                    branch = repository['branch']
                else:
                    branch = None
                if 'cmd' in repository and repository['cmd']:
                    cmd = repository['cmd']
                else:
                    cmd = "git pull"

                if branch in [None, '', self.branch, os.path.basename(self.branch)]:
                    self.log('Updating : %s <= %s' % (path, self.branch))
                    call('git fetch', shell=True)
                    self.log('Executing deploy command :\n' + cmd)
                    call('cd "%s" && %s' % (path, cmd), shell=True)
                # else:
                #     self.log('Do nothing for different branch (%s != %s)' % (branch, self.branch))

    @classmethod
    def log(cls, *messages):
        if cls.quiet:
            logfile = open(cls.LOG_FILE, 'a')
            logtime = time.ctime()
            for msg in messages:
                logfile.write("[%s]%s\n" % (logtime, msg))
            logfile.close()
        else:
            for msg in messages:
                print(msg)

    @classmethod
    def setConfig(cls):
        config = {}
        config['port'] = int(raw_input('*set AutoDeploy Server port:'))
        config['repositories'] = []
        while True:
            cls.log("Add a github repository")
            repository = {}
            giturl = raw_input('*set the git repository url:').strip()
            if not giturl:
                print('Finish setting')
                break

            path = raw_input('*set your local directory(/my/repo):').strip()
            branch = raw_input(' set Branch[None]:').strip()
            if not cls.checkPathWithUrl(path, giturl, branch):
                break

            repository['url'] = giturl
            repository['path'] = path
            repository['branch'] = branch
            repository['cmd'] = raw_input(' set Deploy cmd[None]:').strip()
            config['repositories'].append(repository)

        configfile = open(cls.CONFIG_FILEPATH, 'w')
        configfile.write(json.dumps(config))
        configfile.close()
        cls.log('saving config to ' + cls.CONFIG_FILEPATH)
        return config

    @staticmethod
    def checkPathWithUrl(path, url, branch=None):
        if not path:
            sys.exit('Path can not be None')
        elif not os.path.isdir(path):
            GitAutoDeploy.log('try to create path: ' + path)
            os.makedirs(path)

        if not os.listdir(path):  # empty folder
            if branch:
                cloneCMD = 'git clone -b %s %s "%s"' % (branch, url, path)
            else:
                cloneCMD = 'git clone %s "%s"' % (url, path)
            GitAutoDeploy.log('try : ' + cloneCMD)
            call([cloneCMD], shell=True)
        elif not os.path.isdir(os.path.join(path, '.git')) and not os.path.isdir(os.path.join(path, 'objects')):
            sys.exit('Directory ' + path + ' is not a Git repository')
            return False
        return True


def main():
    try:
        server = None
        for arg in sys.argv:
            if(arg == '-d' or arg == '--daemon-mode'):
                GitAutoDeploy.daemon = True
                GitAutoDeploy.quiet = True
            if(arg == '-q' or arg == '--quiet'):
                GitAutoDeploy.quiet = True

        if(GitAutoDeploy.daemon):
            pid = os.fork()
            if(pid != 0):
                sys.exit()
            os.setsid()

        port = GitAutoDeploy.getConfig()['port']
        server = HTTPServer(('', port), GitAutoDeploy)
        GitAutoDeploy.log('Github Autodeploy Service start listen: %i' % port)
        server.serve_forever()

    except (KeyboardInterrupt, SystemExit) as e:
        GitAutoDeploy.log('stop')
        if(e):
            GitAutoDeploy.log(e)
        if(not server is None):
            server.socket.close()

if __name__ == '__main__':
    main()
