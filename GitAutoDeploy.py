#!/usr/bin/env python

import json
import urlparse
import sys
import os
import time
from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
from subprocess import call


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
                    if not cls.checkPathWithUrl(repository['path'], repository['url']):
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
            urls = self.parseRequest()
            for url in urls:
                self.log(url)
                paths = self.getMatchingPaths(url)
                for path in paths:
                    self.deploy(path)

    def parseRequest(self):
        length = int(self.headers.getheader('content-length'))
        body = self.rfile.read(length)
        payload = json.loads(body)
        self.branch = payload['ref']
        return [payload['repository']['url']]

    def getMatchingPaths(self, repoUrl):
        res = []
        config = self.getConfig()
        for repository in config['repositories']:
            if(repository['url'] == repoUrl):
                res.append(repository['path'])
        return res

    def respond(self, code):
        self.send_response(code)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()

    def deploy(self, path):
        self.log('Updating : ' + path)
        call(['cd "' + path + '" && git fetch'], shell=True)
        config = self.getConfig()
        for repository in config['repositories']:
            if(repository['path'] == path):
                if 'cmd' in repository:
                    branch = None
                    if 'branch' in repository:
                        branch = repository['branch']

                    if branch is None or branch == self.branch:
                        self.log('Executing deploy command :' +
                                 repository['cmd'])
                        call(['cd "' + path + '" && ' +
                              repository['cmd']], shell=True)
                    else:
                        self.log('Push to different branch (%s != %s), not deploying' % (
                            branch, self.branch))
                break

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
            if not cls.checkPathWithUrl(path, giturl):
                break

            repository['url'] = giturl
            repository['path'] = path
            repository['branch'] = raw_input(' set Branch[None]:').strip()
            repository['cmd'] = raw_input(' set Deploy cmd[None]:').strip()
            config['repositories'].append(repository)

        configfile = open(cls.CONFIG_FILEPATH, 'w')
        configfile.write(json.dumps(config))
        configfile.close()
        cls.log('saving config to ' + cls.CONFIG_FILEPATH)
        return config

    @staticmethod
    def checkPathWithUrl(path, url):
        if not path:
            sys.exit('Path can not be None')
        elif not os.path.isdir(path):
            GitAutoDeploy.log('try to create path: ' + path)
            os.makedirs(path)

        if not os.listdir(path):  # empty folder
            cloneCMD = 'git clone %s %s' % (url, path)
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
