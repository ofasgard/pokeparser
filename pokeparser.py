import sys, math, ctypes
import poketext

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
	"hof_trainer_id": 0x0,
	"hof_personality": 0x4,
	"hof_pokedata": 0x8,
	"hof_nickname": 0xA,
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
	"hof_pokemon": 20,
	"hof_trainer_id": 4,
	"hof_personality": 4,
	"hof_pokedata": 2,
	"hof_nickname": 10,
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
		new_buffer = bytearray(self.buffer)
		new_buffer[offsets["save_game_a"]:offsets["save_game_a"]+sizes["save_game_block"]] = self.a.to_bytes()
		new_buffer[offsets["save_game_b"]:offsets["save_game_b"]+sizes["save_game_block"]] = self.b.to_bytes()
		new_buffer[offsets["hall_of_fame"]:offsets["hall_of_fame"]+sizes["hall_of_fame"]] = self.hof.to_bytes()
		new_buffer[offsets["mystery_gift"]:offsets["mystery_gift"]+sizes["mystery_gift"]] = self.mystery_gift.to_bytes()
		new_buffer[offsets["recorded_battle"]:offsets["recorded_battle"]+sizes["recorded_battle"]] = self.recorded_battle.to_bytes()
		return new_buffer
	def write(self, filename):
		fd = open(filename, "wb")
		fd.write(self.to_bytes())
		fd.close()

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
	# TODO: extend with support for specific section types, i.e. trainer data
	def __init__(self, section_buffer, guess_checksum=False):
		self.buffer = section_buffer
		self.data = section_buffer[offsets["section_data"]:offsets["section_data"]+sizes["section_data"]]
		self.id = section_buffer[offsets["section_id"]:offsets["section_id"]+sizes["section_id"]]
		self.checksum = section_buffer[offsets["section_checksum"]:offsets["section_checksum"]+sizes["section_checksum"]]
		self.signature = section_buffer[offsets["section_signature"]:offsets["section_signature"]+sizes["section_signature"]]
		self.save_index = section_buffer[offsets["section_save_index"]:offsets["section_save_index"]+sizes["section_save_index"]]
		
		# Different section types use various numbers of bytes to validate the checksum.
		self.validation_bytes = section_validation_bytes[self.get_id()]
		if guess_checksum:
			self.guess_validation_bytes()

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
		# Read 4 bytes at a time as 32-bit words and add them to the checksum variable.
		checksum = ctypes.c_uint32(0)
		current_offset = 0
		while current_offset < self.validation_bytes:
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
		
	def guess_validation_bytes(self):
		# Experimental. Some ROMHacks change the number of bytes used to validate a section from the defaults.
		# This method tries to figure out what number of bytes are required to produce the pre-existing checksum.
		old_validation_bytes = self.validation_bytes
		
		for i in range(sizes["section_data"], 0, -4):
			self.validation_bytes = i
			checksum = self.generate_checksum()
			if checksum == self.checksum:
				return True
		
		self.validation_bytes = section_validation_bytes[self.get_id()]
		return False
		
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
		
		self.pokemon = []
		for i in range(300):
			# 50 records, each of which contains 6 pokemon
			offset = i * sizes["hof_pokemon"]
			pokemon_buffer = self.buffer[offset:offset+sizes["hof_pokemon"]]
			self.pokemon.append(HallOfFamePokemon(pokemon_buffer))

	def to_bytes(self):
		new_buffer = bytearray(self.buffer)
		for i in range(300):
			offset = i * sizes["hof_pokemon"]
			new_buffer[offset:offset+sizes["hof_pokemon"]] = self.pokemon[i].to_bytes()
		return new_buffer
		
class HallOfFamePokemon:
	def __init__(self, pokemon_buffer):
		self.buffer = pokemon_buffer
		self.trainer_id = pokemon_buffer[offsets["hof_trainer_id"]:offsets["hof_trainer_id"]+sizes["hof_trainer_id"]]
		self.personality = pokemon_buffer[offsets["hof_personality"]:offsets["hof_personality"]+sizes["hof_personality"]]
		self.pokedata = pokemon_buffer[offsets["hof_pokedata"]:offsets["hof_pokedata"]+sizes["hof_pokedata"]]
		self.nickname = pokemon_buffer[offsets["hof_nickname"]:offsets["hof_nickname"]+sizes["hof_nickname"]]

	def get_trainer_id(self):
		return int.from_bytes(self.trainer_id[0:2], "little")
	def get_secret_id(self):
		return int.from_bytes(self.trainer_id[2:4], "little")
	def get_personality(self):
		return int.from_bytes(self.personality, "little")
	def get_species(self):
		# Only the lowest 9 bits are used (little endian byte order).
		# Note that this returns the internal index number, NOT necessarily the national pokedex number.
		# See https://bulbapedia.bulbagarden.net/wiki/List_of_Pok%C3%A9mon_by_index_number_in_Generation_III
		pokedata = int.from_bytes(self.pokedata, "little")
		return pokedata & 0x1FF
	def get_level(self):
		# Only the highest 7 bits are used (little endian byte order).
		pokedata = int.from_bytes(self.pokedata, "little")
		return pokedata >> 9
	def get_nickname(self):
		return poketext.decode_western(self.nickname)
		
	def to_bytes(self):
		new_buffer = bytearray(self.buffer)
		new_buffer[offsets["hof_trainer_id"]:offsets["hof_trainer_id"]+sizes["hof_trainer_id"]] = self.trainer_id
		new_buffer[offsets["hof_personality"]:offsets["hof_personality"]+sizes["hof_personality"]] = self.personality
		new_buffer[offsets["hof_pokedata"]:offsets["hof_pokedata"]+sizes["hof_pokedata"]] = self.pokedata
		new_buffer[offsets["hof_nickname"]:offsets["hof_nickname"]+sizes["hof_nickname"]] = self.nickname
		return new_buffer
		

class MysteryGiftBlock:
	def __init__(self, buffer):
		self.buffer = buffer[offsets["mystery_gift"]:offsets["mystery_gift"]+sizes["mystery_gift"]]
	
	def to_bytes(self):
		new_buffer = bytearray(self.buffer)
		return new_buffer	
		
class RecordedBattleBlock:
	def __init__(self, buffer):
		self.buffer = buffer[offsets["recorded_battle"]:offsets["recorded_battle"]+sizes["recorded_battle"]]
	
	def to_bytes(self):
		new_buffer = bytearray(self.buffer)
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

