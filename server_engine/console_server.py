from __future__ import annotations
from server_engine.server_base import BomberServerBase

import sys
import select
from game_engine.clock import Clock


class ConsoleBomberServer(BomberServerBase):
    """
    Original-ish terminal UI using print/input/select.
    """

    def timed_input(self, prompt: str, timeout: float) -> str | None:
        print(prompt, end="", flush=True)

        ready, _, _ = select.select([sys.stdin], [], [], timeout)

        if ready:
            return sys.stdin.readline().strip()

        print("")
        return None

    def run_lobby(self) -> None:
        ready = False

        while not ready:
            print("")
            print("Hosting a LAN server")

            if len(self.players) > 0:
                print("Players in the lobby")
                for i, player in enumerate(self.players):
                    print(f"{i + 1}: {player.name}")

                inp = self.timed_input("start game? y/n ", timeout=1.0)

                if inp == "y":
                    ready = True

            else:
                print("No players in the lobby")
                Clock.sleep(1)

    def show_scores(self) -> None:
        print("Scoreboard")
        print("=" * 20)

        for name, score in self.get_scoreboard_rows():
            print(f"{name} - {score}")

    def show_end_message(self) -> None:
        print("Game has ended.")

    def show_ping_stats(self, avg_s: float) -> None:
        print(f"average (ns): {self.average_ping} ns")
        print(f"average (s) : {avg_s} s")
        print(f"over pings  : {self.ping_count}")
        print(f"   & pongs  : {self.pong_count}")
