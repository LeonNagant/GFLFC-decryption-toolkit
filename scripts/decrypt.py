# SPDX-FileCopyrightText: 2026 Neptuwunium
#
# SPDX-License-Identifier: EUPL-1.2

import io
from glob import iglob
from pathlib import Path


KEY = b'sdfsdfsdfweerterewwr9ikieioerf[ssfdkjnbnf7t7tt6jfdi354k5kdsdfjksandfgjssijewoowjfsdfoijsdfjsd===-009kskdkdsjsdlkdldlfd[r[hsgswmnckof'
KEYLEN = len(KEY)
MAGIC = b'&\x0A\x0F\x07\x1D  d'
MAGICLEN = len(MAGIC)

def decrypt_data(data: bytes) -> bytearray | bytes:
	if len(data) < MAGICLEN or data[:MAGICLEN] != MAGIC:
		return data

	data = bytearray(data)
	for idx in range(len(data)):
		data[idx] ^= KEY[idx % KEYLEN]

	return data


def decrypt(path: str) -> bytearray:
	info = Path(path)
	if not info.is_file():
		return

	with open(path, 'rb') as f:
		if f.read(MAGICLEN) != MAGIC:
			return

		f.seek(0)
		data = f.read()

	data = decrypt_data(data)

	with open(path, 'wb') as f:
		f.write(data)

	print(path)


if __name__ == '__main__':
	import sys

	for search_path in sys.argv[1:]:
		for path in iglob(search_path, recursive=True):
			decrypt(path)
