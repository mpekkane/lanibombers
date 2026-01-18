"""Music and sound effects handler"""
import os
import arcade
import random
import pyglet.media as media
from typing import List, Optional

SOUND_PATH = os.path.join(os.path.dirname(__file__), "..", "assets", "sounds")
MUSIC_PATH = os.path.join(os.path.dirname(__file__), "..", "assets", "music")


class SoundEngine:
    def __init__(self, music_volume: float, fx_volume: float) -> None:
        self.music_volume = max(min(music_volume, 1.0), 0.0)
        self.fx_volume = max(min(fx_volume, 1.0), 0.0)

        # init sounds
        self._treasure_sound = arcade.load_sound(f"{SOUND_PATH}/KILI.wav")
        self._dig_sound = arcade.load_sound(f"{SOUND_PATH}/PICAXE.wav")
        self._win_sound = arcade.load_sound(f"{SOUND_PATH}/APPLAUSE.wav")
        self._die_sound = arcade.load_sound(f"{SOUND_PATH}/AARGH.wav")
        self._explosion1_sound = arcade.load_sound(f"{SOUND_PATH}/EXPLOS1.wav")
        self._explosion2_sound = arcade.load_sound(f"{SOUND_PATH}/EXPLOS2.wav")
        self._explosion3_sound = arcade.load_sound(f"{SOUND_PATH}/EXPLOS3.wav")
        self._explosion4_sound = arcade.load_sound(f"{SOUND_PATH}/EXPLOS4.wav")
        self._explosion5_sound = arcade.load_sound(f"{SOUND_PATH}/EXPLOS5.wav")
        self._explosions = [
            self._explosion1_sound,
            self._explosion2_sound,
            self._explosion3_sound,
            self._explosion4_sound,
            self._explosion5_sound,
        ]
        self._small_explosion_sound = arcade.load_sound(f"{SOUND_PATH}/PIKKUPOM.wav")
        self._urethane_sound = arcade.load_sound(f"{SOUND_PATH}/URETHAN.wav")
        self._monster = arcade.load_sound(f"{SOUND_PATH}/KARJAISU.wav")

        # init music
        try:
            self._shop_music = arcade.load_sound(f"{MUSIC_PATH}/HUIPPE.wav")
            self._game_music = arcade.load_sound(f"{MUSIC_PATH}/OEKU.wav")
            self._music_enabled = True
        except FileNotFoundError:
            print("No music wavs found. Music disabled")
            self._music_enabled = False
        self._shop_playback: Optional[media.Player] = None
        self._game_playback: Optional[media.Player] = None
        self._playbacks: List[media.Player] = []

    def _play(self, sound: arcade.Sound, loop: bool, volume: float) -> media.Player:
        playback = sound.play(loop=loop, volume=volume)
        self._playbacks.append(playback)
        return playback

    def _play_fx(self, sound: arcade.Sound) -> media.Player:
        return self._play(sound, loop=False, volume=self.fx_volume)

    def _play_music(self, sound: arcade.Sound) -> media.Player:
        return self._play(sound, loop=True, volume=self.music_volume)

    def shop(self) -> None:
        if not self._music_enabled:
            return
        if self._game_playback is not None:
            arcade.stop_sound(self._game_playback)
        self._shop_playback = self._play_music(self._shop_music)

    def game(self) -> None:
        if not self._music_enabled:
            return
        if self._shop_playback is not None:
            arcade.stop_sound(self._shop_playback)
        self._game_playback = self._play_music(self._game_music)

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
