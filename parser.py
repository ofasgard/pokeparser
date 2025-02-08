import sys, math, ctypes

# CONSTANTS

offsets = {
	"save_game_a": 0x0,
	"save_game_b": 0xE000,
	"section_data": 0x0,
	"section_id": 0xFF4,
	"section_checksum": 0xFF6,
	"section_signature": 0xFF8,
	"section_save_index": 0xFFC,
	"hall_of_fame": 0x1C000,
	"mystery_gift": 0x1E000,
	"recorded_battle": 0x1F000
}

sizes = {
	"save_game_block": 57344,
	"section": 4096,
	"section_data": 3968,
	"section_id": 2,
	"section_checksum": 2,
	"section_signature": 4,
	"section_save_index": 4,
	"hall_of_fame": 8192,
	"mystery_gift": 4096,
	"recorded_battle": 4096
}

section_names = {
	0: "Trainer info",
	1: "Team / items",
	2: "Game state",
	3: "Misc data",
	4: "Rival info",
	5: "PC Buffer A",
	6: "PC Buffer B",
	7: "PC Buffer C",
	8: "PC Buffer D",
	9: "PC Buffer E",
	10: "PC Buffer F",
	11: "PC Buffer G",
	12: "PC Buffer H",
	13: "PC Buffer I",
}

section_validation_bytes = {
	0: 3884,
	1: 3968,
	2: 3968,
	3: 3968,
	4: 3848,
	5: 3968,
	6: 3968,
	7: 3968,
	8: 3968,
	9: 3968,
	10: 3968,
	11: 3968,
	12: 3968,
	13: 2000,
}

# CLASSES

class SaveGame:
	def __init__(self, filename):
		fd = open(filename, "rb")
		self.buffer = fd.read()
		fd.close()
		
		self.a = SaveGameBlock(self.buffer, True)
		self.b = SaveGameBlock(self.buffer, False)
		self.hof = HallOfFameBlock(self.buffer)
		self.mystery_gift = MysteryGiftBlock(self.buffer)
		self.recorded_battle = RecordedBattleBlock(self.buffer)
		
	def get_current_save(self):
		# Block A and B are saved to alternately as a backup system. 
		# This method identifies which block is the most recently saved.
		a = self.a.sections[-1].get_save_index()
		b = self.b.sections[-1].get_save_index()
		
		return self.a if a>b else self.b
		
	def to_bytes(self):
		# TODO - implement Mystery Gift and Recorded Battle blocks
		# until that's done, this will return an incomplete save file (suitable for patching only)
		new_buffer = bytearray(sizes["save_game_block"] * 2 + sizes["hall_of_fame"])
		new_buffer[offsets["save_game_a"]:offsets["save_game_a"]+sizes["save_game_block"]] = self.a.to_bytes()
		new_buffer[offsets["save_game_b"]:offsets["save_game_b"]+sizes["save_game_block"]] = self.b.to_bytes()
		new_buffer[offsets["hall_of_fame"]:offsets["hall_of_fame"]+sizes["hall_of_fame"]] = self.hof.to_bytes()
		new_buffer[offsets["mystery_gift"]:offsets["mystery_gift"]+sizes["mystery_gift"]] = self.mystery_gift.to_bytes()
		new_buffer[offsets["recorded_battle"]:offsets["recorded_battle"]+sizes["recorded_battle"]] = self.recorded_battle.to_bytes()
		return new_buffer

class SaveGameBlock:
	def __init__(self, buffer, blockA):
		self.name = "A" if blockA else "B"
	
		offset = offsets["save_game_a"] if blockA else offsets["save_game_b"]
		self.buffer = buffer[offset:offset+sizes["save_game_block"]]

		self.sections = []
		while len(self.sections) < 14:
			offset = len(self.sections) * sizes["section"]
			section_buffer = self.buffer[offset:offset+sizes["section"]]
			section = SaveGameSection(section_buffer)
			self.sections.append(section)

	def get_section_by_name(self, section_name):
		for section in self.sections:
			if section_name.lower() == section.get_name().lower():
				return section
	def get_section_by_id(self, section_id):
		for section in self.sections:
			if section_id == section.get_id():
				return section
				
	def to_bytes(self):
		new_buffer = bytearray(self.buffer)
		for i in range(len(self.sections)):
			offset = sizes["section"] * i
			new_buffer[offset:offset+sizes["section"]] = self.sections[i].to_bytes()
		return new_buffer

class SaveGameSection:
	def __init__(self, section_buffer):
		self.buffer = section_buffer
		self.data = section_buffer[offsets["section_data"]:offsets["section_data"]+sizes["section_data"]]
		self.id = section_buffer[offsets["section_id"]:offsets["section_id"]+sizes["section_id"]]
		self.checksum = section_buffer[offsets["section_checksum"]:offsets["section_checksum"]+sizes["section_checksum"]]
		self.signature = section_buffer[offsets["section_signature"]:offsets["section_signature"]+sizes["section_signature"]]
		self.save_index = section_buffer[offsets["section_save_index"]:offsets["section_save_index"]+sizes["section_save_index"]]

	def get_id(self):
		return int.from_bytes(self.id, "little")
	def get_name(self):
		return section_names[self.get_id()]
	def get_checksum(self):
		return hex(int.from_bytes(self.checksum, "little"))
	def get_signature(self):
		return hex(int.from_bytes(self.signature, "little"))
	def get_save_index(self):
		return int.from_bytes(self.save_index, "little")
		
	def generate_checksum(self):
		# Different section types use various numbers of bytes to validate the checksum.
		validation_bytes = section_validation_bytes[self.get_id()]
		
		# Read 4 bytes at a time as 32-bit words and add them to the checksum variable.
		checksum = ctypes.c_uint32(0)
		current_offset = 0
		while current_offset < validation_bytes:
			current_word = self.data[current_offset:current_offset+4]
			current_value = int.from_bytes(current_word, "little")
			checksum = ctypes.c_uint32(checksum.value + current_value)
			current_offset += 4
		
		# Take the upper 16 bits of the result and add them to the lower 16 bits of the result.
		checksum_bytes = checksum.value.to_bytes(4, "big")
		upper = int.from_bytes(checksum_bytes[0:2], "big")
		lower = int.from_bytes(checksum_bytes[2:4], "big")
		checksum = ctypes.c_uint16(upper + lower)
		
		# This new 16-bit value is the checksum.
		return checksum.value.to_bytes(2, "little")

	def update_checksum(self):
		self.checksum = self.generate_checksum()
		
	def to_bytes(self):
		new_buffer = bytearray(self.buffer)
		new_buffer[offsets["section_data"]:offsets["section_data"]+sizes["section_data"]] = self.data
		new_buffer[offsets["section_id"]:offsets["section_id"]+sizes["section_id"]] = self.id
		new_buffer[offsets["section_checksum"]:offsets["section_checksum"]+sizes["section_checksum"]] = self.checksum
		new_buffer[offsets["section_signature"]:offsets["section_signature"]+sizes["section_signature"]] = self.signature
		new_buffer[offsets["section_save_index"]:offsets["section_save_index"]+sizes["section_save_index"]] = self.save_index
		return new_buffer

class HallOfFameBlock:
	def __init__(self, buffer):
		self.buffer = buffer[offsets["hall_of_fame"]:offsets["hall_of_fame"]+sizes["hall_of_fame"]]
		# TODO actually parse the data
	
	def to_bytes(self):
		new_buffer = bytearray(self.buffer)
		# TODO actually serialize the data
		return new_buffer

class MysteryGiftBlock:
	def __init__(self, buffer):
		self.buffer = buffer[offsets["mystery_gift"]:offsets["mystery_gift"]+sizes["mystery_gift"]]
		# TODO actually parse the data
	
	def to_bytes(self):
		new_buffer = bytearray(self.buffer)
		# TODO actually serialize the data
		return new_buffer	
		
class RecordedBattleBlock:
	def __init__(self, buffer):
		self.buffer = buffer[offsets["recorded_battle"]:offsets["recorded_battle"]+sizes["recorded_battle"]]
		# TODO actually parse the data
	
	def to_bytes(self):
		new_buffer = bytearray(self.buffer)
		# TODO actually serialize the data
		return new_buffer		


# FUNCTIONS

def diff_saves(filename_a, filename_b):
	a = SaveGame(filename_a).get_current_save()
	b = SaveGame(filename_b).get_current_save()	
	
	for i in range(len(a.sections)):
		a_section = a.get_section_by_id(i)
		b_section = b.get_section_by_id(i)
		
		if a_section.data != b_section.data:
			print("Changes identified in {} (addresses relative to section start)".format(a_section.get_name()))
			for byte in range(len(a_section.data)):
				if a_section.data[byte] != b_section.data[byte]:
					print("\t{}: {} => {}".format(hex(byte), a_section.data[byte], b_section.data[byte]))


save = SaveGame("test.sav")

buf = bytearray(save.get_current_save().get_section_by_id(3).data)
buf[0x100] = 0xde
buf[0x101] = 0xad
save.get_current_save().get_section_by_id(3).data = buf

save.get_current_save().get_section_by_id(3).update_checksum()

fd = open("test.sav", "rb+")
fd.write(save.to_bytes())
fd.close()

"""
TODO:

- Extend SaveGameSection for specific section i.e. "Team/items"
- Implement the remaining blocks such as Hall of Fame, and then update SaveGame.to_bytes() so it generates a full valid save file
- Write code for quickly and easily patching savegames, so that I can continue reverse engineering unbound
"""

