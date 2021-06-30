PATHS_FILE = 'paths4.txt'
PLAN_FILE = 'plan.txt'


paths_file = open(PATHS_FILE, "r")
plan_file = open(PLAN_FILE, "w")

plan_file.write("schedule:\n")
all_robots_starts_at_zero_zero = True


for line in paths_file:
    #get and write agent number
    space_idx = line.index(" ")
    colon_idx = line.index(":")
    id = line[space_idx:colon_idx]
    plan_file.write("\tagent"+id.replace(" ", "")+":\n")

    #get sequence of coordinates
    path_string = line[colon_idx+2::]
    path_list = path_string.split('->')

    #parse and write out coordinates
    start_location = []
    counter = 0
    for coord in path_list:
        if coord == '\n' or coord == '':
            continue
        else:
            coord = coord[1:-1]
            y, x = coord.split(',') #this is to compensate for the flipped coordinates that the planner outputs
            if all_robots_starts_at_zero_zero:
                if start_location == []:
                    start_location = [x, y]
                x = str(int(x)-int(start_location[0]))
                y = str(-(int(y)-int(start_location[1])))
            plan_file.write('\t\t- x: ' + x + '\n\t\t y: ' + y + '\n\t\t t: ' + str(counter) + '\n' )
            counter = counter +1


