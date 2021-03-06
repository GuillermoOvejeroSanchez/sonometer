#!/usr/bin/python
# -*- coding: UTF-8 -*-

"""Listen to sound intensity using a microphone"""

import datetime
import csv
from threading import Lock

import pyaudio  # pacman -S portaudio && pip install pyaudio
import numpy as np
import matplotlib

matplotlib.use('TkAgg')
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from tkinter import *
from tkinter.ttk import *

__author__ = 'Dih5'
__version__ = "0.1.0"


class Listener:
    def __init__(self, interval, chunk=1024, data_type=pyaudio.paInt16, channels=1, rate=44100):
        self.interval = interval
        self.chunk = chunk
        self.data_type = data_type
        self.channels = channels
        self.rate = rate

        self.p = pyaudio.PyAudio()
        self.selected_api = 0  # TODO: This is a fixed selection
        self.selected_device = None
        self.audio_stream = None
        self.to_stop = False  # Whether to stop after next callback

        self.lock = Lock()

    def list_api(self):
        """Return the list of available apis"""
        return [self.p.get_host_api_info_by_index(x) for x in range(0, self.p.get_host_api_count())]

    def device_list(self, api=None):
        """Return the list of input devices in the given api"""
        if api is None:
            api = self.selected_api
        devices_in_api = self.list_api()[api]['deviceCount']
        recording_device_list = []
        for x in range(0, devices_in_api):
            device = self.p.get_device_info_by_host_api_device_index(api, x)
            if device['maxInputChannels']:
                recording_device_list.append(device)
        return recording_device_list

    def start(self, callback):
        def wrapped_callback(in_data, frame_count, time_info, status_flags):
            with self.lock:
                callback(in_data)
                if self.to_stop:
                    self.to_stop = False
                    return None, pyaudio.paComplete
                else:
                    return None, pyaudio.paContinue

        if self.audio_stream is not None:
            return False
        if self.selected_device is not None:
            self.audio_stream = self.p.open(format=self.data_type, channels=self.channels, rate=self.rate, input=True,
                                            frames_per_buffer=int(self.rate * self.interval),
                                            stream_callback=wrapped_callback, input_device_index=self.selected_device)
        else:
            self.audio_stream = self.p.open(format=self.data_type, channels=self.channels, rate=self.rate, input=True,
                                            frames_per_buffer=int(self.rate * self.interval),
                                            stream_callback=wrapped_callback)

        self.audio_stream.start_stream()
        return True

    def stop(self):
        if self.audio_stream is None:
            return False
        # If sampling time is too small, this might remain locked.
        # A timeout is used just in case
        if self.lock.acquire(blocking=True, timeout=max(self.interval * 2, 1.0)):
            self.to_stop = True
            self.audio_stream.close()
            self.audio_stream = None
            return True
        else:
            return False

    def terminate(self):
        self.stop()
        self.p.terminate()


class TkListener(Frame):
    def __init__(self, plot_f, data_f=lambda x: x, interval=0.3, master=None, title="TkListener"):
        super().__init__(master=master)
        self.master.title(title)
        self.pack()
        self.figure = Figure(figsize=(5, 4), dpi=100)
        self.active_subplot = self.figure.add_subplot(111)
        self.plot_f = plot_f
        self.data_f = data_f
        self.data = []
        self.lock = Lock()

        # Create a tk.DrawingArea
        self.canvas = FigureCanvasTkAgg(self.figure, master=self)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(side=TOP, fill=BOTH, expand=1)

        self.listener = Listener(interval)
        self.listener.start(self.callback)

        self.after(100, self.update_plot)

    def restart_listener(self, interval):
        if not self.listener.stop():
            return False

        self.listener = Listener(interval)
        self.listener.start(self.callback)
        return True

    def callback(self, in_data):
        with self.lock:
            self.data.append(self.data_f(in_data))

    def update_plot(self):
        """The callback function used to update the plot"""
        with self.lock:
            data = self.data
            self.data = []
        if data:
            for new_data in data:
                self.plot_f(new_data, self.active_subplot)
            self.canvas.draw()
        self.after(100, self.update_plot)


# Tooltip for tk (taken from https://github.com/Dih5/xpecgen)
class CreateToolTip(object):
    """
    A tooltip for a given widget.
    """

    # Based on the content from this post:
    # http://stackoverflow.com/questions/3221956/what-is-the-simplest-way-to-make-tooltips-in-tkinter

    def __init__(self, widget, text, color="#ffe14c"):
        """
        Create a tooltip for an existent widget.
        Args:
            widget: The widget the tooltip is applied to.
            text (str): The text of the tooltip.
            color: The color of the tooltip.
        """
        self.waittime = 500  # miliseconds
        self.wraplength = 180  # pixels
        self.widget = widget
        self.text = text
        self.color = color
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)
        self.widget.bind("<ButtonPress>", self.leave)
        self.id = None
        self.tw = None

    def enter(self, event=None):
        self.schedule()

    def leave(self, event=None):
        self.unschedule()
        self.hidetip()

    def schedule(self):
        self.unschedule()
        self.id = self.widget.after(self.waittime, self.showtip)

    def unschedule(self):
        id = self.id
        self.id = None
        if id:
            self.widget.after_cancel(id)

    def showtip(self, event=None):
        x, y, cx, cy = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 20
        # creates a toplevel window
        self.tw = Toplevel(self.widget)
        # Leaves only the label and removes the app window
        self.tw.wm_overrideredirect(True)
        self.tw.wm_geometry("+%d+%d" % (x, y))
        label = Label(self.tw, text=self.text, justify='left',
                      background=self.color, relief='solid', borderwidth=1,
                      wraplength=self.wraplength)
        label.pack(ipadx=1)

    def hidetip(self):
        tw = self.tw
        self.tw = None
        if tw:
            tw.destroy()


# Specific intensity logic
# From this point code could be moved to a new file to avoid repetition in freqmeter.py


def data_to_intensity(data):
    return np.linalg.norm(np.frombuffer(data, np.int16), 2)


lock = Lock()


class controlled_execution:
    def __enter__(self):
        return lock.__enter__()

    def __exit__(self, type, value, traceback):
        return lock.__exit__(type, value, traceback)


class Streak:
    def __init__(self, points_max):
        self.start_x = None
        self.end_x = None
        self.data = []
        self.points_max = points_max
        pass

    def __len__(self):
        return len(self.data)

    def add_first(self, start_x, start_y):
        self.start_x = start_x
        self.end_x = start_x
        self.data = [start_y]

    def add(self, y):
        if len(self.data) < self.points_max:
            self.end_x = (self.end_x + 1) % self.points_max
        self.data.append(y)

    def mean(self):
        return np.mean(self.data) if len(self) > 0 else 0

    def err(self):
        return np.std(self.data, ddof=1) / np.sqrt(len(self.data)) if len(self) > 1 else 0

    def plot(self, place, color='green', labeled=True):
        if len(self) < 2:
            return
        mean = self.mean()
        err = self.err()
        points_max = self.points_max
        if len(self) >= points_max:  # Covers all plot
            place.plot([0, points_max - 1], [mean, mean], '-', color=color)
            place.fill_between([0, points_max - 1], [mean - err, mean - err], [mean, mean], facecolor=color,
                               alpha=0.5)
            place.fill_between([0, points_max - 1], [mean, mean], [mean + err, mean + err], facecolor=color,
                               alpha=0.5)
            if labeled:
                place.text(points_max / 2, mean + err, u"%.2f ± %.2f" % (mean, err))
        elif self.end_x > self.start_x:  # No anomalies
            place.plot([self.start_x, self.end_x], [mean, mean], '-', color=color)
            place.fill_between([self.start_x, self.end_x], [mean - err, mean - err], [mean, mean],
                               facecolor=color, alpha=0.5)
            place.fill_between([self.start_x, self.end_x], [mean, mean], [mean + err, mean + err],
                               facecolor=color, alpha=0.5)
            if labeled:
                place.text(self.start_x, mean + err, u"%.2f ± %.2f" % (mean, err))
        elif self.end_x < self.start_x:  # Wraps circularly
            place.plot([0, self.end_x], [mean, mean], '-', color=color)
            place.fill_between([0, self.end_x], [mean - err, mean - err], [mean, mean],
                               facecolor=color, alpha=0.5)
            place.fill_between([0, self.end_x], [mean, mean], [mean + err, mean + err],
                               facecolor=color, alpha=0.5)
            place.plot([self.start_x, points_max - 1], [mean, mean], '-', color=color)
            place.fill_between([self.start_x, points_max - 1], [mean - err, mean - err], [mean, mean],
                               facecolor=color, alpha=0.5)
            place.fill_between([self.start_x, points_max - 1], [mean, mean], [mean + err, mean + err],
                               facecolor=color, alpha=0.5)
            if labeled:
                place.text(0, mean + err, u"%.2f ± %.2f" % (mean, err))


class IntensityListener(TkListener):
    def __init__(self, master=None, points_max=80, interval=0.3):
        super().__init__(plot_f=self.intensity_plot, interval=interval, master=master, title="Sonometer")
        self.current_pos = 0
        self.points_max = points_max  # points kept in the plot

        self.recording = False  # Whether a streak is being recorded

        self.streaks = []  # Saved streaks of data

        self.intensity_data = [0] * self.points_max

        # Add specific controls

        self.varStatus = StringVar()
        self.varStatus.set("Sonometer started")
        self.lblStatus = Label(master=self, textvariable=self.varStatus)
        self.lblStatus.pack(side=BOTTOM)

        self.frmOperations = Frame(master=self)
        self.frmOperations.pack(side=BOTTOM)

        self.buttonClearPoints = Button(master=self.frmOperations, text='Clear points', command=self.clear_points)
        self.buttonClearPoints.pack(side=LEFT)

        self.buttonClearStreaks = Button(master=self.frmOperations, text='Clear streaks', command=self.clear_streaks)
        self.buttonClearStreaks.pack(side=LEFT)

        self.buttonStartStreak = Button(master=self.frmOperations, text='Start streak', command=self.start_streak)
        self.buttonStartStreak.pack(side=LEFT)

        self.buttonStopStreak = Button(master=self.frmOperations, text='Stop streak', command=self.stop_streak,
                                       state=DISABLED)
        self.buttonStopStreak.pack(side=LEFT)

        self.buttonCapture = Button(master=self.frmOperations, text='Plot capture', command=self.plot_capture)
        self.buttonCapture.pack(side=LEFT)
        self.ttpCapture = CreateToolTip(self.buttonCapture,
                                        "Save the plot in pdf format.")

        self.frmConfig = Frame(master=self)
        self.frmConfig.pack(side=BOTTOM)

        self.frmInterval = LabelFrame(master=self.frmConfig, text="Sampling per point (s)")
        self.frmInterval.pack(side=LEFT)
        self.varInterval = DoubleVar()
        self.varInterval.set(self.listener.interval)
        self.txtInterval = Entry(master=self.frmInterval, textvariable=self.varInterval)
        self.buttonInterval = Button(master=self.frmInterval, text='Update', command=self.change_interval)
        self.txtInterval.pack(side=TOP)
        self.buttonInterval.pack(side=TOP)
        self.ttpInterval = CreateToolTip(self.buttonInterval,
                                         "Change the sampling time per point to the number above.\nMust be > 0.1 s.")

        self.frmStreakLen = LabelFrame(master=self.frmConfig, text="Streak max points")
        self.frmStreakLen.pack(side=LEFT)
        self.varStreakLen = IntVar()
        self.varStreakLen.set(0)
        self.txtStreakLen = Entry(master=self.frmStreakLen, textvariable=self.varStreakLen)
        self.txtStreakLen.pack(side=TOP)
        self.ttpStreakLen = CreateToolTip(self.txtStreakLen,
                                          "Stop the streak when this number of points is reached. 0 for no automatic stop.")

        self.varStreakToCsv = BooleanVar()
        self.varStreakToCsv.set(True)
        self.chkStreakToCsv = Checkbutton(master=self.frmStreakLen, text="Save streaks", variable=self.varStreakToCsv)
        self.chkStreakToCsv.pack(side=BOTTOM)
        self.ttpStreakToCsv = CreateToolTip(self.chkStreakToCsv,
                                            "If on, the streak will be saved as a csv when completed.")

    def change_interval(self):
        new_interval = self.varInterval.get()
        if new_interval == self.listener.interval:
            self.varStatus.set("Selected interval has not changed")
            return False
        if new_interval < 0.1:
            self.varStatus.set("Too small sampling ignored (min. 0.1).")
            self.varInterval.set(0.1)
            return False
        max_retries = 3
        while max_retries > 0:
            max_retries -= 1
            if self.restart_listener(new_interval):
                self.varStatus.set("Sampling interval set to %g" % new_interval)
                return True
        self.varStatus.set("Unable to change the interval.")
        return False

    def clear_points(self):
        with controlled_execution():
            self.current_pos = 0
            self.intensity_data = [0] * self.points_max

    def clear_streaks(self):
        with controlled_execution():
            self.streaks = []

    def start_streak(self):
        with controlled_execution():
            self.streaks.append(Streak(self.points_max))
            self.recording = True
            self.buttonStopStreak["state"] = "normal"
            self.buttonStartStreak["state"] = "disabled"
            self.buttonClearPoints["state"] = "disabled"
            self.buttonClearStreaks["state"] = "disabled"

    def stop_streak(self):
        with controlled_execution():
            self.recording = False
            self.buttonStartStreak["state"] = "normal"
            self.buttonStopStreak["state"] = "disabled"
            self.buttonClearPoints["state"] = "enabled"
            self.buttonClearStreaks["state"] = "enabled"
            if self.varStreakToCsv.get():
                t = datetime.datetime.now().strftime("%S%M%H%d%m%y")
                file_name = 'data%s.csv' % t
                with open(file_name, 'w', newline='') as csvfile:
                    writer = csv.writer(csvfile, delimiter=',')
                    writer.writerow(self.streaks[-1].data)
                self.varStatus.set("Data saved as %s" % file_name)

    def plot_capture(self):
        with controlled_execution():
            t = datetime.datetime.now().strftime("%S%M%H%d%m%y")
            file_name = "sound" + t + ".pdf"
            self.figure.savefig(file_name)
            self.varStatus.set("Plot saved as " + file_name)

    def intensity_plot(self, in_data, plot):
        self.current_pos += 1
        self.current_pos %= self.points_max
        self.intensity_data[self.current_pos] = data_to_intensity(in_data)
        plot.clear()
        plot.plot(self.intensity_data, 'o')
        plot.plot([self.current_pos], [self.intensity_data[self.current_pos]], 'ro')
        if self.recording:
            if not self.streaks:
                print("Error: tried to record with no streak object")
            else:
                if len(self.streaks[-1]) == 0:
                    self.streaks[-1].add_first(self.current_pos, self.intensity_data[self.current_pos])
                else:
                    self.streaks[-1].add(self.intensity_data[self.current_pos])
                if 0 < self.varStreakLen.get() < len(self.streaks[-1]):
                    self.stop_streak()

        if self.streaks:
            for s in self.streaks[:-1]:
                s.plot(plot, 'yellow')
            self.streaks[-1].plot(plot)

        plot.ticklabel_format(style='sci', axis='y', scilimits=(0, 0))


def main():
    root = Tk()
    app = IntensityListener(root, interval=0.3, points_max=80)
    app.mainloop()


if __name__ == "__main__":
    main()
