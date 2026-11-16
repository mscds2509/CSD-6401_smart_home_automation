"""Command-line dashboard.  Run:  python cli.py"""
import cmd
from main import build_home


class HomeShell(cmd.Cmd):
    intro = "Smart Home CLI - type 'help' for commands, 'quit' to exit."
    prompt = "home> "

    def __init__(self):
        super().__init__()
        self.dash, self.facade, self.sensor = build_home()

    def _ids(self):
        return list(self.dash.get_home_status())

    def _device_command(self, arg, action):
        if arg not in self._ids():
            print(f"Unknown device '{arg}'. Devices: {', '.join(self._ids())}")
        else:
            action(arg)

    def do_status(self, _):
        """status - show every device"""
        for i, s in self.dash.get_home_status().items():
            print(f"  {i:<14} {s}")

    def do_on(self, arg):
        """on <device_id> - turn a device on"""
        self._device_command(arg, self.dash.turn_on_device)

    def do_off(self, arg):
        """off <device_id> - turn a device off"""
        self._device_command(arg, self.dash.turn_off_device)

    def do_alloff(self, _):
        """alloff - turn everything off"""
        self.dash.turn_off_all()

    def do_undo(self, _):
        """undo - undo the last user command"""
        self.dash.undo_last()

    def do_motion(self, _):
        """motion - simulate the hallway motion sensor (triggers automation rules)"""
        self.sensor.detect_motion()

    def do_log(self, _):
        """log - show notifications"""
        for n in self.dash.get_notifications():
            print("  -", n)

    def do_quit(self, _):
        """quit - exit"""
        return True

    do_EOF = do_quit

    def complete_on(self, text, *_):
        return [i for i in self._ids() if i.startswith(text)]

    complete_off = complete_on


if __name__ == "__main__":
    HomeShell().cmdloop()
