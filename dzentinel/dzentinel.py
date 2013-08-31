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

        self.colors = {
            "warn": "#e08e1b",
            "crit": "#ee0d0d",
            "dead": "#8f0d0d",
            "fg_1": "#9d9d9d",
            "fg_2": "#666666",
            "fg_3": "#a8c410",
            "bg_1": "#111117",
            "bg_2": "#66770a",
            "bg_3": "#292929",
            "icon": "#a8c410",
            "sep": "#a8c411",
        }

        self.icons = join(
            os.getenv('HOME'),
            '.local/share/infect/misc/x11/dzentinel/icons'
        )

        self.checkhost = "google.com"

        self.pac_count = "/dev/shm/fakepacdb/counts"

    def run(self):
        # print('Starting')

        # TODO: Unhack this from dir() pls :(
        for name in dir(self):
            value = getattr(self, name)
            if hasattr(value, 'runner'):
                t = threading.Thread(None, value)
                t.daemon = False
                t.start()

    def write(self, fn, value):
        # print("Writing {0} to {1}".format(value, fn))

        path = join(self.cwd, fn)
        with open(path, 'w') as fp:
            fp.write(str(value))

    def icon(self, icon, fg=None, bg=None):
        if fg is None:
            fg = "icon"
        icon = "^i(%s)" % join(self.icons, "%s.xbm" % icon)
        return "%s" % self.colorize(
            icon,
            fg=fg,
            bg=bg
        )

    def colorize(self, text, fg=None, bg=None):
        fg = self.colors[fg] if fg is not None else self.colors["fg_1"]
        bg = self.colors[bg] if bg is not None else self.colors["bg_1"]
        return "^fg(%s)^bg(%s)%s^fg()^bg()" % (fg, bg, text)

    @interval(1)
    def date(self):
        now = datetime.datetime.now()
        day = self.colorize(now.strftime("%a,"), fg="fg_2")
        date = self.colorize(now.strftime("%Y.%m.%d"))
        timestamp = self.colorize(now.strftime("%H:%M:%S"))
        return "%s %s %s %s" % (
            day,
            date,
            self.colorize("@", fg="fg_3"),
            timestamp
        )

    # TODO: Use inotify on interface data
    @interval(20)
    def network(self):
        try:
            ip = self.colorize(
                socket.gethostbyname(socket.gethostname()),
                "fg_1"
            )
            # TODO: Please fix
            if "127.0.0" in ip:
                raise OSError
            ip = self.colorize(ip)
            icon = self.icon("wifi_01")
        except (OSError, Exception):
            ip = self.colorize("N/A", "dead")
            icon = self.icon("wifi_01", fg="dead")

        return "%s %s" % (icon, ip)

    @interval(1)
    def load(self):
        elevated_load = False
        load_avgs = ""
        for avg in os.getloadavg():
            if avg < 1:
                load_avgs += "%s " % self.colorize(avg)
            elif avg < 3:
                load_avgs += "%s " % self.colorize(avg, fg="warn")
                if elevated_load != "crit":
                    elevated_load = "warn"
            else:
                load_avgs += "%s " % self.colorize(avg, fg="crit")
                elevated_load = "crit"

            icon = self.icon("scorpio")
            if elevated_load:
                icon = self.icon("scorpio", fg=elevated_load)

        return "%s %s" % (icon, load_avgs[:-1])

    @interval(5)
    def processes(self):
        processes = len(psutil.get_pid_list())
        if processes < 300:
            processes = self.colorize(processes)
            icon = self.icon("cpu")
        elif processes < 600:
            processes = self.colorize(processes, "warn")
            icon = self.icon("cpu", fg="warn")
        else:
            processes = self.colorize(processes, "crit")
            icon = self.icon("cpu", fg="warn")

        return "%s %s" % (icon, processes)

    @interval(5)
    def mem_swap(self):
        icon = self.icon("mem")
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        return "%s %s%s%s" % (
            icon,
            self.colorize(int(mem.free / 1024**2), fg="fg_2"),
            self.colorize("/", fg="fg_1"),
            self.colorize(int(swap.used / 1024**2), fg="fg_2")
        )

    @interval(10)
    def packages(self):
        icon = self.icon("pacman")
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
        ).communicate()

        pkgs = sub.Popen(
            ['pacman', '-Q'],
            stdout=sub.PIPE
        ).communicate()[0].decode()
        pkgs = self.colorize(len(pkgs.split("\n")) if len(pkgs) > 0 else 0)

        new_pkgs = sub.Popen(
            ['pacman', '--dbpath', fakedb, '-Qqu'],
            stdout=sub.PIPE
        ).communicate()[0].decode()
        new_pkgs = len(new_pkgs.split("\n")) if len(new_pkgs) > 0 else 0
        if new_pkgs == 0:
            new_pkgs = self.colorize(new_pkgs)
        else:
            new_pkgs = self.colorize(new_pkgs, "crit")
            icon = self.icon("pacman", fg="crit")

        return "%s %s%s%s" % (
            icon,
            pkgs,
            self.colorize("/", fg="fg_3"),
            new_pkgs
        )

    @interval(1)
    def volume(self):
        volume = alsaaudio.Mixer().getvolume()[0]
        muted = alsaaudio.Mixer().getmute()[0]
        if volume < 35:
            icon = self.icon("spkr_02")
        else:
            icon = self.icon("spkr_01")

        if muted:
            volume = "%s %s" % (
                self.colorize(volume, fg="fg_2"),
                self.colorize("(Mute)", fg="dead")
            )
        else:
            volume = self.colorize(volume)

        return "%s %s" % (icon, volume)

    @static
    def hostname(self):
        return socket.gethostname()

    @static
    def kernel(self):
        icon = self.icon("arch")
        out = sub.Popen(['uname', '-r'], stdout=sub.PIPE).communicate()
        kernel = str(re.sub(r'\s', '', out[0].decode()))
        return "%s %s" % (icon, kernel)

    @interval(10)
    def power(self):
        acpi = sub.Popen(
            ['acpi', '-ab'], stdout=sub.PIPE
        ).communicate()[0].decode().split("\n")

        percent_match = re.search("\d{1,3}%", acpi[0])
        percent = int(percent_match.group(0)[:-1])

        ac_connected = False
        time_left = ""
        if "on-line" in acpi[1]:
            ac_connected = True
        else:
            time_match = re.search("\d{2}:\d{2}:\d{2}", acpi[0])
            if time_match and len(time_match.group(0)) >= 5:
                time_left = self.colorize(
                    "(%s)" % time_match.group(0)[:5],
                    fg="fg_2"
                )

        if percent < 10:
            icon = self.icon("bat_empty_01", fg="crit")
            percent = self.colorize(str(percent) + "%", fg="crit")
        elif percent < 20:
            icon = self.icon("bat_empty_01", fg="warn")
            percent = self.colorize(str(percent) + "%", fg="warn")
        elif percent < 30:
            icon = self.icon("bat_low_01", fg="warn")
            percent = self.colorize(str(percent) + "%")
        elif percent < 50:
            icon = self.icon("bat_low_01")
            percent = self.colorize(str(percent) + "%")
        elif percent < 80:
            icon = self.icon("bat_full_01")
            percent = self.colorize(str(percent) + "%")
        else:
            icon = self.icon("bat_full_01")
            percent = self.colorize(str(percent) + "%", fg="fg_3")

        ret = "%s %s" % (icon, percent)

        if ac_connected:
            ret = "%s %s" % (
                self.icon("ac_01"),
                ret
            )
        elif time_left:
            ret += " %s" % time_left

        return ret


def main():
    dzentinel = Dzentinel()
    dzentinel.setup()
    dzentinel.run()


if __name__ == '__main__':
    main()
