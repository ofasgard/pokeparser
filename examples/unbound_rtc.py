#!/usr/bin/env python3

"""
In Pokemon Unbound, an NPC in Frozen Heights will reset your real-time clock if it gets desynced. 
However, they will only ever do this once per save. This script patches your save file so that they'll reset the RTC for you again.
Tested on version 2.1.1.1 of Pokemon Unbound.
"""

import sys

sys.path.append('../')
import pokeparser

save = pokeparser.SaveGame(sys.argv[1])
current = save.get_current_save()

# The relevant flag is stored in the "rival info" save game block.
section = current.get_section_by_id(4)
buf = bytearray(section.data)
buf[0xe89] = 0
section.data = buf

# No need to update the checksum, because unbound doesn't actually check this byte for validation.

save.write("patched.sav")
