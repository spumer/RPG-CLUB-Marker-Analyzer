# encoding: utf-8

import analyze


def print_dupe():
	dupes = analyze.get_dupes()

	if not dupes:
		print("Sorry, dupe not found")
	else:
		print("Great! Dupe was found!")
		for dupe in dupes:
			print(
				dupe.to_msg(),
				end='\n\n'
			)


if __name__ == '__main__':
	import code
	print_dupe()
	code.InteractiveConsole().raw_input(prompt='Press Enter to exit...')
