#!/usr/bin/env python

import os
import re
import time
import socket
import threading
import datetime
import subprocess as sub

from os.path import join

import alsaaudio
import psutil


def interval(sleep):
    def real_decorator(function):
        def wrapper(self, *args, **kwargs):
            while True:
                ret = function(self)

                fn = function.__name__
                self.write(fn, ret)

                time.sleep(sleep)

        wrapper.runner = True
        return wrapper
    return real_decorator


def static(function):
    def wrapper(self, *args, **kwargs):
        ret = function(self)

        fn = function.__name__
        self.write(fn, ret)

    wrapper.runner = True
    return wrapper


class Dzentinel(object):
    def setup(self):
        xdg = os.getenv(
            'XDG_CACHE_HOME',
            join(os.getenv('HOME'), '.cache')
        )

        p = join(xdg, 'dzentinel')
        os.makedirs(p, exist_ok=True)

        self.cwd = p

    def run(self):
        print('Starting')

        # TODO: Unhack this from dir() pls :(
        for name in dir(self):
            value = getattr(self, name)
            if hasattr(value, 'runner'):
                t = threading.Thread(None, value)
                t.daemon = False
                t.start()

    def write(self, fn, value):
        print("Writing {0} to {1}".format(value, fn))

        path = join(self.cwd, fn)
        with open(path, 'w') as fp:
            fp.write(str(value))

    @interval(1)
    def date(self):
        return datetime.datetime.now().strftime("%Y.%m.%d, %H:%M:%S")

    # TODO: Use inotify on interface data
    @interval(20)
    def network(self):
        try:
            ip = socket.gethostbyname(socket.gethostname())
            return ip
        except (OSError, Exception):
            return "N/A"

    @interval(1)
    def load(self):
        load = os.getloadavg()
        return "%.2f %.2f %.2f" % load

    @interval(5)
    def processes(self):
        return len(psutil.get_pid_list())

    @interval(5)
    def memory(self):
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        return "%s/%s" % (int(mem.free / 1024**2), int(swap.used / 1024**2))

    @interval(10)
    def packages(self):
        fakedb = join("/dev", "shm", "fakepacdb")
        fakelock = join(fakedb, "db.lck")
        # realdb = join("/var", "lib", "pacman")

        os.makedirs(join(fakedb, "sync"), exist_ok=True)

        if os.path.exists(fakelock):
            os.remove(join(fakedb, "db.lck"))

        # if not os.path.islink(join(fakedb, "local")):
            # os.symlink(join(realdb, "local"), fakedb)

        sub.Popen(
            ['fakeroot', 'pacman', '--dbpath', fakedb, '-Sy'],
            stdout=sub.PIPE
        ).communicate()

        pkgs = sub.Popen(
            ['pacman', '-Q'],
            stdout=sub.PIPE
        ).communicate()[0]
        pkgs = pkgs.decode()
        pkgs = len(pkgs.split("\n")) if len(pkgs) > 0 else 0

        new_pkgs = sub.Popen(
            ['pacman', '--dbpath', fakedb, '-Qqu'],
            stdout=sub.PIPE
        ).communicate()[0]
        new_pkgs = new_pkgs.decode()
        new_pkgs = len(new_pkgs.split("\n")) if len(new_pkgs) > 0 else 0

        return "%s %s" % (pkgs, new_pkgs)

    @interval(1)
    def volume(self):
        return alsaaudio.Mixer().getvolume()[0]

    @static
    def hostname(self):
        return socket.gethostname()

    @static
    def kernel(self):
        out = sub.Popen(['uname', '-r'], stdout=sub.PIPE).communicate()
        ret = re.sub(r'\s', '', out[0].decode())
        return str(ret)

    @interval(10)
    def battery(self):
        return 100


def main():
    dzentinel = Dzentinel()
    dzentinel.setup()
    dzentinel.run()


if __name__ == '__main__':
    main()
