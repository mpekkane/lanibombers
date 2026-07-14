import time
from pyenttec import DMXConnection
import yaml
import random
import threading
from game_engine.clock import Clock
from enum import IntEnum
from typing import Tuple


class DMX:
    def __init__(self, config_path: str = "cfg/dmx_config.yaml") -> None:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        usb_device = config["device"]
        self.devices = config["ports"]

        self.dmx = DMXConnection(usb_device)

    def get_devices(self):
        return self.devices

    def set(
        self,
        address: int,
        red: int = 0,
        green: int = 0,
        blue: int = 0,
        white: int = 0,
        amber: int = 0,
        uv: int = 0,
        strobe: int = 0,
        motor: int = 0,
        auto: int = 0,
    ) -> None:
        # Nine channels used by one Diamond Dome.
        values = [
            red,
            green,
            blue,
            white,
            amber,
            uv,
            strobe,
            motor,
            auto,
        ]
        start_index = address - 1

        for offset, value in enumerate(values):
            if not 0 <= value <= 255:
                raise ValueError(f"DMX value must be 0..255, got {value}")

            self.dmx.dmx_frame[start_index + offset] = value

    def set_all(
        self,
        red: int = 0,
        green: int = 0,
        blue: int = 0,
        white: int = 0,
        amber: int = 0,
        uv: int = 0,
        strobe: int = 0,
        motor: int = 0,
        auto: int = 0,
    ):
        for device in self.devices:
            self.set(device, red, green, blue, white, amber, uv, strobe, motor, auto)

    def send(self):
        self.dmx.render()


class LightingState(IntEnum):
    INIT = 1
    SERVER = 2
    SERVER_ALERT = 3
    SHOP = 4
    GAME = 5
    WIN = 6
    FX = 100


class LightingEffects:
    # How long each effect occupies the lights. Events that happened during
    # that interval are overlapping and should not be replayed later.
    FX_DURATIONS = {
        "small_bomb": 0.2,
        "medium_bomb": 0.3,
        "big_bomb": 0.4,
        "strobe_bomb": 0.5,
        "nuke": 3.5,
    }

    # Override-order template. An incoming effect can interrupt the currently
    # playing effect only when its priority is higher.
    FX_PRIORITY = {
        "small_bomb": 1,
        "medium_bomb": 2,
        "big_bomb": 3,
        "strobe_bomb": 4,
        "nuke": 5,
    }

    def __init__(self, config_path: str = "cfg/dmx_config.yaml") -> None:
        self.dmx = DMX(config_path)
        self.devices = self.dmx.get_devices()

        self.dmx.set_all()
        self.running = True
        self.fx_queue = []
        self.fx_queue_lock = threading.Lock()
        self.current_fx = None
        self.fx_interrupted = threading.Event()
        self.fx_thread = threading.Thread(target=self.run_fx)
        self.state = LightingState.INIT
        self.prev_state = LightingState.INIT
        self.win_color: Tuple[int, int, int] = (-1, -1, -1)
        self.alert_started = -1
        self.alert_limit = 0.5
        self.alert_mode = False

    def stop(self):
        self.running = False
        self.fx_interrupted.set()
        self.fx_thread.join()

    def start(self):
        self.running = True
        self.fx_thread.start()

    # ███████╗████████╗ █████╗ ████████╗███████╗███████╗
    # ██╔════╝╚══██╔══╝██╔══██╗╚══██╔══╝██╔════╝██╔════╝
    # ███████╗   ██║   ███████║   ██║   █████╗  ███████╗
    # ╚════██║   ██║   ██╔══██║   ██║   ██╔══╝  ╚════██║
    # ███████║   ██║   ██║  ██║   ██║   ███████╗███████║
    # ╚══════╝   ╚═╝   ╚═╝  ╚═╝   ╚═╝   ╚══════╝╚══════╝

    def server_alert(self):
        self.state = LightingState.SERVER_ALERT

    def server(self):
        self.alert_time = 0
        self.state = LightingState.SERVER

    def shop(self):
        self.state = LightingState.SHOP

    def game(self):
        self.state = LightingState.GAME

    def win(self, r: int, g: int, b: int):
        self.win_color = (r, g, b)
        self.state = LightingState.WIN

    # ███████╗██╗   ██╗███████╗███╗   ██╗████████╗███████╗
    # ██╔════╝██║   ██║██╔════╝████╗  ██║╚══██╔══╝██╔════╝
    # █████╗  ██║   ██║█████╗  ██╔██╗ ██║   ██║   ███████╗
    # ██╔══╝  ╚██╗ ██╔╝██╔══╝  ██║╚██╗██║   ██║   ╚════██║
    # ███████╗ ╚████╔╝ ███████╗██║ ╚████║   ██║   ███████║
    # ╚══════╝  ╚═══╝  ╚══════╝╚═╝  ╚═══╝   ╚═╝   ╚══════╝

    def small_bomb(self):
        self._queue_fx("small_bomb")

    def medium_bomb(self):
        self._queue_fx("medium_bomb")

    def big_bomb(self):
        self._queue_fx("big_bomb")

    def strobe_bomb(self):
        self._queue_fx("strobe_bomb")

    def nuke(self):
        self._queue_fx("nuke")

    # ██╗      ██████╗  ██████╗ ██╗ ██████╗
    # ██║     ██╔═══██╗██╔════╝ ██║██╔════╝
    # ██║     ██║   ██║██║  ███╗██║██║
    # ██║     ██║   ██║██║   ██║██║██║
    # ███████╗╚██████╔╝╚██████╔╝██║╚██████╗
    # ╚══════╝ ╚═════╝  ╚═════╝ ╚═╝ ╚═════╝

    def _queue_fx(self, name: str):
        with self.fx_queue_lock:
            fx = (name, Clock.now())
            overrides_current = (
                self.current_fx is not None
                and self.FX_PRIORITY[name] > self.FX_PRIORITY[self.current_fx]
            )
            if overrides_current:
                # Put the override next, ahead of lower-priority effects that
                # accumulated while the current effect was playing.
                priority = self.FX_PRIORITY[name]
                insert_at = next(
                    (
                        index
                        for index, (queued_name, _) in enumerate(self.fx_queue)
                        if self.FX_PRIORITY[queued_name] < priority
                    ),
                    len(self.fx_queue),
                )
                self.fx_queue.insert(insert_at, fx)
                self.fx_interrupted.set()
            else:
                self.fx_queue.append(fx)

    def run_fx(self):
        last_fx_name = None
        last_fx_started_at = None
        last_fx_duration = 0.0
        name = ""

        while self.running:
            with self.fx_queue_lock:
                fx = self.fx_queue.pop(0) if self.fx_queue else None
                queue_was_empty = fx is None
                if fx is not None:
                    self.state = LightingState.FX
                    name, queued_at = fx

                    # Overlapping effects are normally skipped. A higher-
                    # priority effect is the exception: it replaces the
                    # lower-priority effect immediately.
                    overlaps_previous = (
                        last_fx_started_at is not None
                        and queued_at < last_fx_started_at + last_fx_duration
                    )
                    overrides_previous = (
                        overlaps_previous
                        and self.FX_PRIORITY[name] > self.FX_PRIORITY[last_fx_name]
                    )
                    if overlaps_previous and not overrides_previous:
                        fx = None
                    else:
                        last_fx_name = name
                        last_fx_started_at = queued_at
                        last_fx_duration = self.FX_DURATIONS[name]
                        self.current_fx = name
                        self.fx_interrupted.clear()

            if fx is None:
                if queue_was_empty:
                    if self.state != self.prev_state:
                        if self.state == LightingState.FX:
                            self.state = self.prev_state

                        self.prev_state = self.state
                        if self.state == LightingState.SERVER:
                            self._server_fx()
                        elif self.state == LightingState.SERVER_ALERT:
                            self._server_alert_fx()
                        elif self.state == LightingState.SHOP:
                            self._shop_fx()
                        elif self.state == LightingState.GAME:
                            self._game_fx()
                        elif self.state == LightingState.WIN:
                            self._win_fx()
                    else:
                        if self.state == LightingState.SERVER_ALERT:
                            self._server_alert_fx()
                        time.sleep(0.1)
                continue

            try:
                if name == "small_bomb":
                    self._small_bomb_fx()
                elif name == "medium_bomb":
                    self._medium_bomb_fx()
                elif name == "big_bomb":
                    self._big_bomb_fx()
                elif name == "strobe_bomb":
                    self._strobe_bomb_fx()
                elif name == "nuke":
                    self._nuke_fx()
            finally:
                with self.fx_queue_lock:
                    self.current_fx = None

    def random_bomb(self):
        r = random.random()
        if r <= 0.25:
            return self.small_bomb()
        elif r > 0.25 and r <= 0.5:
            return self.medium_bomb()
        elif r > 0.5 and r <= 0.75:
            return self.big_bomb()
        else:
            return self.strobe_bomb()

    def stop_fx(self):
        self.state = LightingState.INIT
        self.prev_state = LightingState.INIT
        with self.fx_queue_lock:
            self.fx_queue.clear()
            self.fx_interrupted.set()

        self.dmx.set_all()
        self.dmx.send()

    def _wait(self, seconds: float) -> bool:
        """Wait for an effect step, returning True when it was interrupted."""
        return self.fx_interrupted.wait(seconds)

    # ██████╗  ██████╗ ███╗   ███╗██████╗ ███████╗
    # ██╔══██╗██╔═══██╗████╗ ████║██╔══██╗██╔════╝
    # ██████╔╝██║   ██║██╔████╔██║██████╔╝███████╗
    # ██╔══██╗██║   ██║██║╚██╔╝██║██╔══██╗╚════██║
    # ██████╔╝╚██████╔╝██║ ╚═╝ ██║██████╔╝███████║
    # ╚═════╝  ╚═════╝ ╚═╝     ╚═╝╚═════╝ ╚══════╝

    def _small_bomb_fx(self):
        self.dmx.set_all(red=32, amber=64)
        self.dmx.send()
        if self._wait(0.1):
            return

        self.dmx.set_all(red=8, amber=16)
        self.dmx.send()
        if self._wait(0.1):
            return

        self.dmx.set_all(red=0, amber=0)
        self.dmx.send()

    def _medium_bomb_fx(self):
        self.dmx.set_all(red=64, amber=128)
        self.dmx.send()
        if self._wait(0.1):
            return

        self.dmx.set_all(red=32, amber=64)
        self.dmx.send()
        if self._wait(0.1):
            return

        self.dmx.set_all(red=8, amber=16)
        self.dmx.send()
        if self._wait(0.1):
            return

        self.dmx.set_all(red=0, amber=0)
        self.dmx.send()

    def _big_bomb_fx(self):
        self.dmx.set_all(red=128, amber=255)
        self.dmx.send()
        if self._wait(0.1):
            return

        self.dmx.set_all(red=64, amber=128)
        self.dmx.send()
        if self._wait(0.1):
            return

        self.dmx.set_all(red=32, amber=64)
        self.dmx.send()
        if self._wait(0.1):
            return

        self.dmx.set_all(red=8, amber=16)
        self.dmx.send()
        if self._wait(0.1):
            return

        self.dmx.set_all(red=0, amber=0)
        self.dmx.send()

    def _strobe_bomb_fx(self):
        r = random.randint(64, 128)
        a = random.randint(128, 255)
        w = random.randint(0, 128)
        s = random.randint(64, 200)
        self.dmx.set_all(red=r, amber=a, white=w, strobe=s)
        self.dmx.send()
        if self._wait(0.5):
            return

        self.dmx.set_all(red=0, amber=0)
        self.dmx.send()

    def _nuke_fx(self):
        self.dmx.set_all(white=255, red=255, amber=255, strobe=200, motor=0)
        self.dmx.send()
        if self._wait(1):
            return

        self.dmx.set_all(white=128, red=128, amber=128, strobe=0, motor=240)
        self.dmx.send()
        if self._wait(0.5):
            return

        self.dmx.set_all(white=64, red=64, amber=64, strobe=0, motor=240)
        self.dmx.send()
        if self._wait(0.5):
            return

        self.dmx.set_all(white=32, red=32, amber=32, strobe=0, motor=240)
        self.dmx.send()
        if self._wait(0.5):
            return

        self.dmx.set_all(white=16, red=16, amber=16, strobe=0, motor=240)
        self.dmx.send()
        if self._wait(0.5):
            return

        self.dmx.set_all(white=8, red=8, amber=8, strobe=0, motor=240)
        self.dmx.send()
        if self._wait(0.5):
            return

        self.dmx.set_all()
        self.dmx.send()

    # ███████╗████████╗ █████╗ ████████╗███████╗    ███████╗██╗  ██╗
    # ██╔════╝╚══██╔══╝██╔══██╗╚══██╔══╝██╔════╝    ██╔════╝╚██╗██╔╝
    # ███████╗   ██║   ███████║   ██║   █████╗      █████╗   ╚███╔╝
    # ╚════██║   ██║   ██╔══██║   ██║   ██╔══╝      ██╔══╝   ██╔██╗
    # ███████║   ██║   ██║  ██║   ██║   ███████╗    ██║     ██╔╝ ██╗
    # ╚══════╝   ╚═╝   ╚═╝  ╚═╝   ╚═╝   ╚══════╝    ╚═╝     ╚═╝  ╚═╝

    def _win_fx(self):
        (r, g, b) = self.win_color
        self.dmx.set_all(red=r, green=g, blue=b, motor=200)
        self.dmx.send()

    def _server_fx(self):
        self.dmx.set_all(green=128, motor=128)
        self.dmx.send()

    def _server_alert_fx(self):
        dt = Clock.now() - self.alert_started
        run = False
        if self.alert_started < 0:
            run = True
        if dt > self.alert_limit:
            run = True
        if run:
            for i, dev in enumerate(self.devices):
                if self.alert_mode:
                    effi = i+1
                else:
                    effi = i
                if effi % 2 == 0:
                    self.dmx.set(dev, red=250, motor=240)
                else:
                    self.dmx.set(dev, blue=250, motor=240)
            self.dmx.send()
            self.alert_started = Clock.now()
            self.alert_mode = not self.alert_mode

    def _shop_fx(self):
        self.dmx.set_all(auto=100, motor=200)
        self.dmx.send()

    def _game_fx(self):
        self.dmx.set_all(uv=64, motor=128)
        self.dmx.send()
