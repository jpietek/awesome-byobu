"""Fedora KDE/GNOME wake/unlock timestamps, subscribed once through D-Bus."""
import time
from .collector import atomic_write


def watch(state_dir):
    try:
        from gi.repository import Gio, GLib
    except ImportError as error:
        raise RuntimeError("Install python3-gobject-base for Fedora KDE event integration") from error

    def wake(connection, sender, path, interface, signal, parameters, data):
        if parameters.unpack() == (False,):
            atomic_write(state_dir / "last-wake", str(int(time.time())) + "\n")

    def unlock(connection, sender, path, interface, signal, parameters, data):
        if parameters.unpack() == (False,):
            atomic_write(state_dir / "last-unlock", str(int(time.time())) + "\n")

    system = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
    session = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    system.signal_subscribe("org.freedesktop.login1", "org.freedesktop.login1.Manager", "PrepareForSleep",
                            "/org/freedesktop/login1", None, Gio.DBusSignalFlags.NONE, wake, None)
    session.signal_subscribe("org.freedesktop.ScreenSaver", "org.freedesktop.ScreenSaver", "ActiveChanged",
                             None, None, Gio.DBusSignalFlags.NONE, unlock, None)
    session.signal_subscribe("org.gnome.ScreenSaver", "org.gnome.ScreenSaver", "ActiveChanged",
                             None, None, Gio.DBusSignalFlags.NONE, unlock, None)
    GLib.MainLoop().run()
