"""
A small random number generator that gives the same numbers in Python and in the browser.

Python's own `random` cannot be reproduced in JavaScript, so the live pages could never be
checked against the Python model. This one is mulberry32 (32-bit state), with Box-Muller
for normal draws; src/dash/fg_engine.js has the same three functions, and
tests/test_fg_parity.py checks that both give the same results for the same seed.
"""
import math

MASK = 0xFFFFFFFF


class PortableRandom:
    def __init__(self, seed):
        self.s = int(seed) & MASK

    def random(self):
        """Uniform in [0, 1), identical to the JavaScript mulberry32."""
        self.s = (self.s + 0x6D2B79F5) & MASK
        t = self.s
        t = ((t ^ (t >> 15)) * (t | 1)) & MASK
        t = ((t + (((t ^ (t >> 7)) * (t | 61)) & MASK)) & MASK) ^ t
        return ((t ^ (t >> 14)) & MASK) / 4294967296.0

    def gauss(self, mu=0.0, sigma=1.0):
        u1 = 1.0 - self.random()               # (0, 1], keeps log finite
        u2 = self.random()
        return mu + sigma * math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)

    def randint(self, a, b):
        return a + int(math.floor(self.random() * (b - a + 1)))
