import matplotlib as mpl
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from statistics import mode
import time
import astar

from matplotlib.widgets import Button

from natnet.protocol import RigidBody, LabeledMarker, Position, Rotation
import random

import itertools
from shapely.geometry import LineString
from enum import Enum


class CellVal(Enum):
    EMPTY = 0
    ORIGIN = 1
    ROBOT_FULL = 2 #entire robot is on one cell
    ROBOT_PARTIAL = 3 #robot is spread out over multiple cells
    OBSTACLE_REAL = 4
    OBSTACLE_ART = 5 #artificial obstacle


class Grid:
    # A class that holds a grid and can visualize this grid, export it as a map file, or export it as scene file
    def __init__(self, x_dim:int=10, y_dim:int=6, cell_size:float=1.0, map_filename:str='my_map.map', scen_filename:str= 'my_scene.scen'):
        # arena dimensions (within greater 12x12 scope)
        self.x_dim = min(x_dim, 12)  # m
        self.y_dim = min(y_dim, 12)  # m
        self.cell_size = cell_size  # m
        self.rows = int(12 / cell_size)  # TODO shouldn't this be x_dim instead of 12?
        self.cols = int(12 / cell_size)  # TODO shouldn't this be y_dim instead of 12?
        self.origin_cell = [int(np.floor(self.cols / 2)), int(np.floor(self.rows / 2))]

        # the grid itself with values
        self.grid = []
        self.reset_grid()

        # variables related to matplotlib visualization
        self.fig = None
        self.ax = None
        self.cMap = mpl.colors.ListedColormap(['w', 'r', 'k', 'y', 'c', 'm']) #TODO: fix colors and map nicely to cellval values
        self.heatmap = None

        # variables related to exporting map and scene files
        self.mapfile = map_filename
        self.scenfile = scen_filename
        self.endspots = []

        #association of robots with their ID
        self.bots = {}

    def reset_grid(self):
        # reset the grid so that all values are 0 (meaning nothing is in the box)
        self.grid = []
        for i in range(int(self.rows)):
            self.grid.append([CellVal.EMPTY.value for i in range(int(self.cols))])
        self.bots = {}

    def getBlockedCells(self, vertices_list, dr=0.01): #TODO: make it so that this only uses the outer vertices??? waste of time if there's a body with a lot of inner markers
        blocked_cells = []
        for pair in itertools.product(vertices_list, repeat=2):
            line_blocked_cells = self.lineGridIntersection(pair[0], pair[1], dr)
            # blocked_cells.append(line_blocked_cells)
            blocked_cells += line_blocked_cells
        return list(set(blocked_cells))

    def add_body(self, type, body_coords, tolerance=1):
        #a word on tolerance: it describes how "strict" the system will be with requiring a robot to be in one cell in order to count it as a robot
        #   tolerance of 0: zero tolerance, all of a robot's markers must be in one cell
        #   tolerance of 1: all markers but one should be in the same cell
        #   tolerance of 2: higher flexibility, just goes with the majority\
        #if the robot's configuration is outside of the specified tolerance, it will highlight all the cells the robot touches
        # if type is obstacle, then color all the cells it touches
        if type == -1: #obstacle
            blocked_cells = self.getBlockedCells(body_coords)
            for coord in blocked_cells:
               self.grid[coord[0]][coord[1]] = CellVal.OBSTACLE_REAL.value
        # if type is robot, then if it's mostly concentrated on one cell color it, if it's spread out color all of them
        else: #robot
            relevant_cells = [self.xy_to_cell(coord) for coord in body_coords]
            mode_cell = mode(relevant_cells)
            majority_count = len(relevant_cells) / 2
            # print(relevant_cells)
            if tolerance == 0 and relevant_cells.count(mode_cell) == len(relevant_cells):#all cells are in one
                self.grid[mode_cell[0]][mode_cell[1]] = CellVal.ROBOT_FULL.value
                self.bots[type] = [mode_cell[0], mode_cell[1]]
            elif tolerance == 1 and relevant_cells.count(mode_cell) >= len(relevant_cells) - 1:#all cells but one are in the same cell
                self.grid[mode_cell[0]][mode_cell[1]] = CellVal.ROBOT_FULL.value
                self.bots[type] = [mode_cell[0], mode_cell[1]]
            elif tolerance == 2 and relevant_cells.count(mode_cell) >= majority_count:#majority cells are in the same cell
                self.grid[mode_cell[0]][mode_cell[1]] = CellVal.ROBOT_FULL.value
                self.bots[type] = [mode_cell[0], mode_cell[1]]
            else:
                # highlight all the cells it touches
                for cell in relevant_cells:
                    self.grid[cell[0]][cell[1]] = CellVal.ROBOT_PARTIAL.value

    def lineGridIntersection(self, p1, p2, dr):
        ls = LineString([p1, p2])
        points_on_line = []
        line_length = np.ceil(ls.length)
        num_samples = int(line_length / dr)
        linespace = [x * dr for x in range(0, num_samples + 1)]
        for f in linespace:
            p = ls.interpolate(f).coords[0]

            points_on_line.append(p)

        ar = np.array(points_on_line, 'f')

        cells = list(map(lambda p: self.xy_to_cell(p), ar))
        return cells

    def restrict_arena(self):
        # goal: place artificial obstacles around the perimeter of our desired arena
        x = int(self.x_dim / self.cell_size)
        y = int(self.y_dim / self.cell_size)
        # corners
        top_right = [(self.origin_cell[0] - y // 2), self.origin_cell[1] + x // 2]
        bottom_right = [(self.origin_cell[0] + y // 2), self.origin_cell[1] + x // 2]
        top_left = [(self.origin_cell[0] - y // 2), self.origin_cell[1] - x // 2]
        bottom_left = [(self.origin_cell[0] + y // 2), self.origin_cell[1] - x // 2]
        corners = [top_left, top_right, bottom_right, bottom_left]
        borders = corners
        for i in range(top_left[1], top_right[1]): # top border
            borders.append([top_right[0], i])
        for i in range(bottom_left[1], bottom_right[1]): # bottom border
            borders.append([bottom_right[0], i])
        for i in range(top_left[0], bottom_left[0]): # left border
            borders.append([i, bottom_left[1]])
        for i in range(top_right[0], bottom_right[0]): # right border
            borders.append([i, bottom_right[1]])
        # indicate all relevant cells in the grid
        for cell in borders:
            self.grid[cell[0]][cell[1]] = CellVal.OBSTACLE_ART.value

    def plot_init_heatmap(self):
        # initialize heatmap to be used to display the plot; should be called before plot_render()
        self.fig, self.ax = plt.subplots(1, 1)
        bounds = range(self.cMap.N)
        norm = mpl.colors.BoundaryNorm(bounds, self.cMap.N)
        data = self.grid
        self.heatmap = self.ax.pcolor(data, edgecolors='k', linewidths=1, cmap=self.cMap, norm=norm)
        self.fig.canvas.draw()
        plt.gca().invert_yaxis()
        self.fig.show()

    def plot_render(self):

        # re-plot grid with up-to-date values; should be called after updating/adding values
        self.restrict_arena()
        data = self.grid
        # color origin cell
        data[self.origin_cell[0]][self.origin_cell[1]] = CellVal.ORIGIN.value
        if self.heatmap == None:
            self.plot_init_heatmap()
        bounds = range(self.cMap.N)
        norm = mpl.colors.BoundaryNorm(bounds, self.cMap.N)
        self.heatmap = self.ax.pcolormesh(data, edgecolors='k', linewidths=1, cmap=self.cMap, norm=norm)

        axprev = plt.axes([0.7, 0.02, 0.1, 0.075])
        axnext = plt.axes([0.81, 0.02, 0.1, 0.075])
        bnext = Button(axnext, 'Map')
        bnext.on_clicked(self.make_map)
        bprev = Button(axprev, 'Scenario')
        bprev.on_clicked(self.make_scen)

        self.ax.draw_artist(self.ax.patch)
        self.ax.draw_artist(self.heatmap)
        self.fig.canvas.blit(self.ax.bbox)
        self.fig.canvas.flush_events()
        # t_end = time.time()
        plt.pause(0.2)

    def xy_to_cell(self, loc):
        # convert x and y from Motive to new coordinate system
        x = -loc[0]
        y = -loc[1]
        return (int(self.origin_cell[0] + np.round(x / self.cell_size)), int(self.origin_cell[1] + np.round(y / self.cell_size)))


    def make_map(self, event=None):
        f = open(self.mapfile, "w")
        f.write("type octile\n")
        f.write("height " + str(self.rows) + '\n')
        f.write("width " + str(self.cols) + '\n')
        f.write("map\n")
        for i in range(int(self.rows)):
            for j in range(int(self.cols)):
                if self.grid[i][j] == CellVal.OBSTACLE_ART.value or self.grid[i][j] == CellVal.OBSTACLE_REAL.value:
                    f.write('@')
                else:
                    f.write('.')
            f.write('\n')
        f.close()

    def make_scen(self, event=None):
        # for each ROBOT on the grid (meaning its grid value is 1), make a line with all its info
        f = open(self.scenfile, "w")
        f.write("version 1\n")
        print(self.bots)
        for key, value in self.bots.items():
            # bucket
            f.write(str(key)+'\t')
            print("writing out", key)
            # .map file name
            f.write(str(self.mapfile) + '\t')
            # dimensions of the grid
            f.write(str(int(self.rows)) + '\t' + str(int(self.cols)) + '\t')
            # starting position
            f.write(str(value[0]) + '\t' + str(value[1]) + '\t')
            # ending position
            x, y = self.get_empty_spot()
            f.write(str(x) + '\t' + str(y) + '\t')
            # optimal distance
            f.write("\n")
            # f.write(f'{self.get_optimal_length((i, j), (x, y))}\n')
        f.close()
        print("should be done")

    def get_empty_spot(self):
        try_x = -1
        try_y = -1
        while True:
            try_x = random.randint(0, self.cols)
            try_y = random.randint(0, self.rows)
            if self.grid[try_x][try_y] != 0:
                continue
            for coord in self.endspots: # now need to make sure no two ending spots align
                if coord[0] == try_x and coord[1] == try_y:
                    continue
            break
        self.endspots.append([try_x, try_y])
        return try_x, try_y

    def get_optimal_length(self, loc1, loc2):
        path = list(astar.find_path(loc1, loc2,
                                    neighbors_fnct=lambda loc: self.neighbors(loc, True),
                                    heuristic_cost_estimate_fnct=self.heuristic,
                                    distance_between_fnct=self.distance))

        dist = 0
        prev = path[0]
        for p in path[1:]:
            dist += self.distance(prev, p)
            prev = p

        return dist

    def neighbors(self, loc, diagonal_moves=False):
        moves = [
            np.array([0, 1]),
            np.array([1, 0]),
            np.array([0, -1]),
            np.array([-1, 0])
        ]
        if diagonal_moves:
            moves += [
                np.array([1, 1]),
                np.array([-1, 1]),
                np.array([1, -1]),
                np.array([-1, -1])
            ]
        neighbors = []
        for move in moves:
            new_loc = np.array(loc) + move
            if 0 <= new_loc[0] <= self.cols-1 and 0 <= new_loc[1] <= self.rows-1 and self.grid[new_loc[0]][new_loc[1]] == 0:
                neighbors.append(tuple(new_loc))

        return neighbors

    def heuristic(self, loc, goal):
        return np.linalg.norm(np.array(loc)-np.array(goal), 2)

    def distance(self, loc1, loc2):
        return np.linalg.norm(np.array(loc1)-np.array(loc2), 2)


if __name__ == "__main__":
    # Testing the optimal length function
    env = Grid(12, 12)
    m, n = env.rows, env.cols
    start_x = np.random.randint(0, m)
    start_y = np.random.randint(0, n)
    goal_x = np.random.randint(0, m)
    goal_y = np.random.randint(0, n)

    print(env.get_optimal_length((start_x, start_y), (goal_x, goal_y)))


