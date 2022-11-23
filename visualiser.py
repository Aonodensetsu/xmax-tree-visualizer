# import required libraries
import os
import sys
import csv
import math
import tkinter
import matplotlib

# force mpl to use tkinter - it's bundled with python
matplotlib.use('TkAgg', force=True)
import matplotlib.pyplot as plot

# fix for running via left click (changes cwd to file location)
os.chdir(os.path.dirname(os.path.realpath(__file__)))

# try to import PY effect
if os.path.exists('tree_effect.py'):
	import tree_effect

# create global dataframes
positions = []  # {x, y, z} per LED
frames = []  # {t: 1/frame rate, c: [{r, g, b} per LED, normalized]} per frame


# get tree coordinates
def get_tree():
	print('Loading tree coordinates')
	global positions
	# overwrite table to prevent data corruption
	positions = []
	# read coordinates or create cone
	if os.path.exists('coordinates.csv'):
		with open('coordinates.csv', mode='r', encoding='utf-8-sig') as f:
			for line in f.readlines():
				x, y, z = line.split(',')
				positions.append({'x': float(x), 'y': float(y), 'z': float(z)})
		return True
	else:
		print('No coordinates supplied - creating placeholder')
		theta = 0
		height = 0.006
		for _ in range(499):
			radius = (0.006*510-height)/3.6
			positions.append({'x': radius * math.cos(theta), 'y': radius * math.sin(theta), 'z': height})
			# some magic to make the points (more) evenly spaced
			theta = (theta + 0.174533/math.pow(radius, 3/5)) % 6.28319
			height += 0.006
		# add a final point at the very middle to make the top look better
		positions.append({'x': 0, 'y': 0, 'z': height+0.012})
		return False


# compile PY effect to CSV and preview
def generate_csv():
	global positions
	print('Generating CSV - will preview from PY as it renders')
	# create the csv header string
	# the string if very long, so construct it programmatically
	with open('tree_effect.csv', mode='w') as f:
		string = 'FRAME_TIME'
		for i in range(500):
			for j in ['R', 'G', 'B']:
				string += f',{j}_{i}'
		f.write(f'{string}\n')
	# get frame information from py effect
	frame = 1
	frame_max = tree_effect.frame_max()
	frame_time = round(1 / tree_effect.frame_rate(), 7)
	# initialize empty storage for effect
	storage = None
	# make a GUI to preview while generating
	graph = gui()
	# create effect csv
	# if interrupted will not corrupt csv and will produce a valid file
	# albeit cut in the middle (it updates the file once per frame)
	with open('tree_effect.csv', mode='a+') as f:
		while frame <= frame_max:
			# get current frame from effect
			storage, colors = tree_effect.run(storage, positions, frame)
			# preview while creating
			draw(graph, {'t': 1/tree_effect.frame_rate(), 'c': colors})
			# create csv string for all leds
			string = f'{frame_time}'
			for led in colors:
				for c in 'rgb':
					# csv spec is not normalized
					string += f',{int(led[c]*255)}'
			# update CSV file
			f.write(f'{string}\n')
			frame += 1
	# return GUI to continue playback
	return graph


# read frame descriptions from XTREE
def read_xtree():
	global frames
	# overwrite table to prevent corruption
	frames = []
	print('Reading XTREE')
	bytes_total = os.path.getsize('tree_effect.xtree')
	with open('tree_effect.xtree', mode='br+') as xf:
		leds = int.from_bytes(xf.read(2), 'big')
		frame_num = int((bytes_total - 2) / (leds * 3 + 2))
		for _ in range(frame_num):
			frame_time = 1/int.from_bytes(xf.read(2), 'big')
			colors = []
			for _ in range(leds):
				colors.append({
					'r': float(int.from_bytes(xf.read(1), 'big'))/255,
					'g': float(int.from_bytes(xf.read(1), 'big'))/255,
					'b': float(int.from_bytes(xf.read(1), 'big'))/255
				})
			frames.append({'t': frame_time, 'c': colors})


# read frame descriptions from CSV
def read_csv():
	global frames
	print('Reading CSV')
	with open('tree_effect.csv', mode='r', encoding='utf-8-sig') as f:
		reader = list(csv.reader(f))[1:]
		# overwrite table to prevent corruption
		frames = [
			{'t': float(line[0]), 'c': [
				{
					# csv is not normalized, normalize values here
					'r': float(line[3*i-2])/255,
					'g': float(line[3*i-1])/255,
					'b': float(line[3*i])/255
				}
				for i in range(1, int((len(reader[0]) - 1) / 3) + 1)
			]}
			for line in reader
		]


# create CSV file from internal representation
def create_csv():
	global frames
	print('Creating CSV')
	# create the csv header string
	# the string if very long, so construct it programmatically
	with open('tree_effect.csv', mode='w') as f:
		string = 'FRAME_TIME'
		for i in range(500):
			for j in ['R', 'G', 'B']:
				string += f',{j}_{i}'
		f.write(f'{string}\n')
	with open('tree_effect.csv', mode='a+') as f:
		for i in frames:
			string = str(round(i['t'], 7))
			for j in i['c']:
				for k in ['r', 'g', 'b']:
					string += ','+str(int(j[k]*255))
			f.write(string+'\n')


# create XTREE file from internal representation
def create_xtree():
	global frames
	print('Creating XTREE')
	with open('tree_effect.xtree', mode='bw+') as xf:
		# amount of LEDs
		xf.write(int(len(frames[0]['c'])).to_bytes(2, 'big'))
		# for each animation frame
		for i in frames:
			xf.write(int(1/i['t']).to_bytes(2, 'big'))
			# for each LED
			for j in i['c']:
				# for each RGB
				for k in ['r', 'g', 'b']:
					xf.write(int(j[k]*255).to_bytes(1, 'big'))


# check the existence of files that change app behavior
def get_state():
	print('Checking available files')
	# state is a binary value for available files
	state = 0
	# is a PY effect available?
	if 'tree_effect' in sys.modules:
		state += 1
	# is a CSV effect available?
	if os.path.exists('tree_effect.csv'):
		state += 1 << 1
	# is an XTREE effect available?
	if os.path.exists('tree_effect.xtree'):
		state += 1 << 2
	# are coordinates available?
	if get_tree():
		state += 1 << 3
	return state


# create visualizer window
def gui():
	# don't draw anything if importing, but still allow creating a csv by calling main()
	if not __name__ == '__main__':
		return None
	print('Initializing GUI')
	# measure screen size and dpi
	screen_measurer = tkinter.Tk()
	dpi = screen_measurer.winfo_fpixels('1i')
	screen_height = screen_measurer.winfo_screenheight()
	# compute a sensible size for the visualizer
	top = int(0.05 * screen_height)
	height = int(0.8 * screen_height)
	left = 100
	width = int(0.9 * height)
	screen_measurer.update()
	screen_measurer.destroy()
	# create window
	matplotlib.rcParams['toolbar'] = 'None'
	matplotlib.rc('grid', color='None')
	window = plot.figure(num='Christmas Tree Visualiser')
	# move and resize window
	window.canvas.manager.window.wm_geometry(f'+{left}+{top}')
	window.set_size_inches(width / dpi, height / dpi)
	# stop plotting when window closed
	window.canvas.mpl_connect('close_event', lambda e: plot.close(window))
	# create 3d plot
	graph = window.add_subplot(111, projection='3d')
	# set camera position
	graph.view_init(elev=15, azim=5)
	# set background colors
	window.patch.set_facecolor('#4c4a48')
	graph.set(fc='#4c4a48')
	graph.xaxis.pane.set_alpha(0)
	graph.yaxis.pane.set_alpha(0)
	graph.zaxis.pane.set_alpha(0)
	# set labels
	graph.set_xlabel('X', color='white', labelpad=-5)
	graph.set_ylabel('Y', color='white', labelpad=-5)
	graph.set_zlabel('Z', color='white', labelpad=5)
	graph.set(xlim3d=(-1, 1), ylim3d=(-1, 1), zlim3d=(0, max([p['z'] for p in positions])))
	graph.set(xticks=[-1, 1], yticks=[-1, 1], zticks=[0, max([p['z'] for p in positions])])
	graph.margins(x=0, y=0, z=0, tight=True)
	graph.tick_params(which='both', color='None', labelcolor='white')
	graph.tick_params(axis='both', pad=5)
	graph.tick_params(axis='z', pad=15)
	# plot 'wires' connecting leds
	graph.plot([p['x'] for p in positions], [p['y'] for p in positions], [p['z'] for p in positions], color=(0, 0, 0, 0.08))
	# set correct aspect ratio
	graph.set_box_aspect([ub - lb for lb, ub in (getattr(graph, f'get_{a}lim')() for a in 'xyz')])
	# shrink window borders
	plot.tight_layout()
	return graph


# update plot
def draw(graph, frame):
	global positions
	# ignore calls if no window exists
	if not plot.fignum_exists(1):
		return
	# clear the previous frame
	for dot in plot.gca().collections:
		dot.remove()
	# plot current values
	graph.scatter3D(
		[p['x'] for p in positions],
		[p['y'] for p in positions],
		[p['z'] for p in positions],
		c=[(led['r'], led['g'], led['b']) for led in frame['c']]
	)
	# draw for frame_time
	plot.draw()
	plot.pause(frame['t'])


def main():
	global positions, frames
	state = get_state()
	match state:
		# 0 - (nothing loaded)     show a placeholder tree with black LEDs
		# 2 - (csv loaded)         ignore CSV since there are no coordinates -> 0
		# 4 - (xtree loaded)       ignore XTREE since there are no coordinates -> 0
		# 6 - (csv, xtree loaded)  ignore CSV & XTREE -> 0
		# 8 - (coordinates loaded) show the tree with black LEDs
		case 0 | 2 | 4 | 6 | 8:
			# create window
			graph = gui()
			# draw gui with a fake frame
			draw(graph, {'t': 1/30, 'c': [{'r': 0, 'g': 0, 'b': 0} for _ in positions]})
			plot.show()
		# 1 - (py loaded)             show on a placeholder tree
		# 3 - (py, csv loaded)        ignore CSV -> 1
		# 5 - (py, xtree loaded)      ignore XTREE -> 1
		# 7 - (py, csv, xtree loaded) ignore CSV & XTREE -> 1
		case 1 | 3 | 5 | 7:
			# set up frame counters
			frame = 1
			# give storage to the PY effect
			storage = None
			# create window
			graph = gui()
			while plot.fignum_exists(1):
				# reset from beginning
				if not frame <= tree_effect.frame_max():
					frame = 1
				# get current frame from effect
				storage, colors = tree_effect.run(storage, positions, frame)
				draw(graph, {'t': 1/tree_effect.frame_rate(), 'c': colors})
				frame += 1
		# 9 - (py, coordinates loaded) play the PY effect and generate static files
		case 9:
			# create a csv
			print('Coordinates loaded - will compile to CSV')
			graph = generate_csv()
			# when CSV created, read its contents
			print('Compiled - will load and preview from CSV, check for errors')
			read_csv()
			# create a smaller representation of the effect
			create_xtree()
			# get frames from csv
			frame = 1
			# preview while window open
			while plot.fignum_exists(1):
				# restart from beginning
				if not frame <= len(frames):
					frame = 1
				# update plot
				draw(graph, frames[frame-1])
				frame += 1
		# 10 - (csv, coordinates loaded)     play back the CSV, generate XTREE
		# 11 - (py, csv, coordinates loaded) ignore PY since csv exists -> 10
		case 10 | 11:
			read_csv()
			create_xtree()
			# set up frame counters
			frame = 1
			# create window
			graph = gui()
			# while GUI open, update plot
			while plot.fignum_exists(1):
				# restart from beginning
				if not frame <= len(frames):
					frame = 1
				# update plot
				draw(graph, frames[frame-1])
				frame += 1
		# 12 - (xtree, coordinates)          play back the XTREE, generate CSV
		# 13 - (py, xtree, coordinates)      ignore PY since XTREE exists -> 12
		# 14 - (csv, xtree, coordinates)     ignore CSV -> 12
		# 15 - (py, csv, xtree, coordinates) ignore PY and CSV -> 12
		case 12 | 13 | 14 | 15:
			read_xtree()
			# don't overwrite an existing CSV
			if state < 14:
				create_csv()
			# set up frame counters
			frame = 1
			# create window
			graph = gui()
			# while GUI open, update plot
			while plot.fignum_exists(1):
				# restart from beginning
				if not frame <= len(frames):
					frame = 1
				# update plot
				draw(graph, frames[frame - 1])
				frame += 1


# import guard
if __name__ == '__main__':
	main()
