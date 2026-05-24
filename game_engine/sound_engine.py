"""Music and sound effects handler"""

import os
import arcade
import random
import pyglet.media as media
from typing import List, Optional
from game_engine.clock import Clock

SOUND_PATH = os.path.join(os.path.dirname(__file__), "..", "assets", "sounds")
MUSIC_PATH = os.path.join(os.path.dirname(__file__), "..", "assets", "music")


class SoundEngine:
    def __init__(self, music_volume: float, fx_volume: float) -> None:
        self.music_volume = max(min(music_volume, 1.0), 0.0)
        self.fx_volume = max(min(fx_volume, 1.0), 0.0)

        # init sounds
        self._treasure_sound = arcade.load_sound(f"{SOUND_PATH}/KILI.mp3")
        self._dig_sound = arcade.load_sound(f"{SOUND_PATH}/PICAXE.mp3")
        self._win_sound = arcade.load_sound(f"{SOUND_PATH}/APPLAUSE.mp3")
        self._die_sound = arcade.load_sound(f"{SOUND_PATH}/AARGH.mp3")
        self._explosion1_sound = arcade.load_sound(f"{SOUND_PATH}/EXPLOS1.mp3")
        self._explosion2_sound = arcade.load_sound(f"{SOUND_PATH}/EXPLOS2.mp3")
        self._explosion3_sound = arcade.load_sound(f"{SOUND_PATH}/EXPLOS3.mp3")
        self._explosion4_sound = arcade.load_sound(f"{SOUND_PATH}/EXPLOS4.mp3")
        self._explosion5_sound = arcade.load_sound(f"{SOUND_PATH}/EXPLOS5.mp3")
        self._explosions = [
            self._explosion1_sound,
            self._explosion2_sound,
            self._explosion3_sound,
            self._explosion4_sound,
            self._explosion5_sound,
        ]
        self._small_explosion_sound = arcade.load_sound(f"{SOUND_PATH}/PIKKUPOM.mp3")
        self._urethane_sound = arcade.load_sound(f"{SOUND_PATH}/URETHAN.mp3")
        self._monster = arcade.load_sound(f"{SOUND_PATH}/KARJAISU.mp3")

        # init music
        try:
            self._shop_music = arcade.load_sound(f"{MUSIC_PATH}/kauppa.mp3")
            self._game_music_1 = arcade.load_sound(f"{MUSIC_PATH}/biisi1.mp3")
            self._game_music_2 = arcade.load_sound(f"{MUSIC_PATH}/biisi2.mp3")
            self._game_music_3 = arcade.load_sound(f"{MUSIC_PATH}/biisi3.mp3")
            self._game_music_4 = arcade.load_sound(f"{MUSIC_PATH}/biisi4.mp3")
            self._game_music_5 = arcade.load_sound(f"{MUSIC_PATH}/biisi5.mp3")
            self._game_music = [
                self._game_music_1,
                self._game_music_2,
                self._game_music_3,
                self._game_music_4,
                self._game_music_5,
            ]
            self._music_enabled = True
        except FileNotFoundError:
            print("No music mp3s found. Music disabled")
            self._music_enabled = False
        self._shop_playback: Optional[media.Player] = None
        self._game_playback: Optional[media.Player] = None
        self._playbacks: List[media.Player] = []

    def _play(self, sound: arcade.Sound, loop: bool, volume: float) -> media.Player:
        playback = sound.play(loop=loop, volume=volume, speed=1.0, pan=0.0)
        self._playbacks.append(playback)
        return playback

    def _play_fx(self, sound: arcade.Sound) -> media.Player:
        return self._play(sound, loop=False, volume=self.fx_volume)

    def _play_music(self, sound: arcade.Sound, loop: bool = False) -> media.Player:
        return self._play(sound, loop=loop, volume=self.music_volume)

    def shop(self) -> None:
        if not self._music_enabled:
            return
        if self._game_playback is not None:
            arcade.stop_sound(self._game_playback)
        self._shop_playback = self._play_music(self._shop_music, loop=True)

    def game(self) -> None:
        if not self._music_enabled:
            return
        if self._shop_playback is not None:
            arcade.stop_sound(self._shop_playback)
        song = random.choice(self._game_music)
        self._game_playback = self._play_music(song)

        @self._game_playback.event
        def on_player_eos():
            self.game()

    def scoreboard(self) -> None:
        player = self._play_fx(self._win_sound)

        @player.event
        def on_player_eos():
            self.shop()

    def stop_music(self) -> None:
        if self._game_playback is not None:
            arcade.stop_sound(self._game_playback)
        if self._shop_playback is not None:
            arcade.stop_sound(self._shop_playback)

    def stop_all(self) -> None:
        for playback in self._playbacks:
            arcade.stop_sound(playback)

    def treasure(self) -> None:
        self._play_fx(self._treasure_sound)

    def die(self) -> None:
        self._play_fx(self._die_sound)

    def win(self) -> None:
        self._play_fx(self._win_sound)

    def dig(self) -> None:
        self._play_fx(self._dig_sound)

    def explosion(self) -> None:
        # FIXME: these might actually be linked to bomb type, have to check
        sound = random.choice(self._explosions)
        self._play_fx(sound)

    def small_explosion(self) -> None:
        self._play_fx(self._small_explosion_sound)

    def urethane(self) -> None:
        self._play_fx(self._urethane_sound)

    def monster(self) -> None:
        self._play_fx(self._monster)

    def diagnostics(self) -> None:
        print("Sound diagnostics")

        sounds = [
            (self._treasure_sound,"_treasure_sound"),
            (self._dig_sound,"_dig_sound"),
            (self._win_sound,"_win_sound"),
            (self._die_sound,"_die_sound"),
            (self._explosion1_sound,"_explosion1_sound"),
            (self._explosion2_sound,"_explosion2_sound"),
            (self._explosion3_sound,"_explosion3_sound"),
            (self._explosion4_sound,"_explosion4_sound"),
            (self._explosion5_sound,"_explosion5_sound"),
            (self._small_explosion_sound,"_small_explosion_sound"),
            (self._urethane_sound,"_urethane_sound"),
            (self._monster,"_monster"),
            (self._shop_music,"_shop_music"),
            (self._game_music_1,"_game_music_1"),
            (self._game_music_2,"_game_music_2"),
            (self._game_music_3,"_game_music_3"),
            (self._game_music_4,"_game_music_4"),
            (self._game_music_5,"_game_music_5"),
        ]

        for sound, name in sounds:
            print(f"PLay: {name}")
            playback = self._play(sound, loop=False, volume=1.0)
            Clock.sleep(1)
            self.stop_all()
