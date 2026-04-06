import turtle as T
import math

vertices = []

def click_handler(x, y):
    try:
        vertices.append((x, y))
        T.goto(x, y)
        T.dot(5, "red")
        if len(vertices) > 1:
            T.pendown()
            T.goto(vertices[-2])
            T.penup()
    except Exception as e:
        print(f"Error: {e}")
        reset_code()

def right_click_handler(x, y):
    try:
        T.penup()
        T.onscreenclick(None)  # Disable further screen clicks
        draw_and_fill_poly(vertices, "grey")
        
        # Draw the start and end points
        T.penup()
        T.goto(start)
        T.dot(robot_radius * 2 + 10, "green")  # Make the start point bigger
        T.write("Start", align="center", font=("Arial", 12, "bold"))
        T.goto(end)
        T.dot(robot_radius * 2 + 10, "red")    # Make the end point bigger
        T.write("End", align="center", font=("Arial", 12, "bold"))

        # Draw solid lines connecting the vertices of the polygon
        draw_polygon_edges(vertices)

        # Find and draw the path for the robot
        inflated_vertices = inflate_polygon(vertices, 15)
        path = find_path_around_polygon(start, end, inflated_vertices)
        if path:
            draw_path(path, color="blue")
        else:
            print("No valid path found.")
        
        # Add label to top left-hand corner
        T.penup()
        T.goto(-390, 270)  # Adjusted position
        T.write("Blue line = Path Taken", align="left", font=("Arial", 12, "bold"))

        T.done()
    except Exception as e:
        print(f"Error: {e}")
        reset_code()

def draw_and_fill_poly(P, colour="grey"):
    """ Draws and fills a polygon given a list of vertices """
    try:
        T.color(colour)
        T.penup()
        T.goto(P[0])
        T.begin_fill()
        T.pendown()
        for p in P[1:]:
            T.goto(p)
        T.goto(P[0])
        T.end_fill()
        T.penup()
    except Exception as e:
        print(f"Error: {e}")
        reset_code()

def draw_polygon_edges(vertices):
    """ Draws solid lines connecting the vertices of the polygon """
    try:
        T.color("black")
        T.penup()
        T.goto(vertices[0])
        T.pendown()
        for vertex in vertices[1:]:
            T.goto(vertex)
        T.goto(vertices[0])
        T.penup()
    except Exception as e:
        print(f"Error: {e}")
        reset_code()

def inflate_polygon(vertices, distance):
    """ Inflates the polygon by a given distance """
    expanded = []
    for i in range(len(vertices)):
        p1 = vertices[i]
        p2 = vertices[(i + 1) % len(vertices)]
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        length = math.hypot(dx, dy)
        offset_x = distance * dy / length
        offset_y = -distance * dx / length
        expanded.append((p1[0] + offset_x, p1[1] + offset_y))
        expanded.append((p2[0] + offset_x, p2[1] + offset_y))
    return expanded

def find_path_around_polygon(start, end, vertices):
    """ Finds a path from start to end avoiding the polygon """
    try:
        path = a_star(start, end, vertices)
        return path
    except Exception as e:
        print(f"Error: {e}")
        reset_code()

def a_star(start, end, vertices):
    """ A* pathfinding algorithm """
    open_set = [start]
    came_from = {}
    g_score = {start: 0}
    f_score = {start: heuristic(start, end)}

    while open_set:
        current = min(open_set, key=lambda x: f_score.get(x, float('inf')))
        open_set.remove(current)

        if current == end:
            return reconstruct_path(came_from, current)

        for neighbor in get_neighbors(current):
            if not does_intersect(current, neighbor, vertices):
                tentative_g_score = g_score[current] + heuristic(current, neighbor)
                if neighbor not in g_score or tentative_g_score < g_score[neighbor]:
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g_score
                    f_score[neighbor] = g_score[neighbor] + heuristic(neighbor, end)
                    if neighbor not in open_set:
                        open_set.append(neighbor)

    return None

def get_neighbors(point):
    """ Returns neighboring points (adjacent grid cells) """
    neighbors = [
        (point[0] + 20, point[1]), (point[0] - 20, point[1]),
        (point[0], point[1] + 20), (point[0], point[1] - 20),
        (point[0] + 20, point[1] + 20), (point[0] - 20, point[1] - 20),
        (point[0] + 20, point[1] - 20), (point[0] - 20, point[1] + 20)
    ]
    return neighbors

def reconstruct_path(came_from, current):
    """ Reconstructs the path from the came_from map """
    total_path = [current]
    while current in came_from:
        current = came_from[current]
        total_path.append(current)
    total_path.reverse()
    return total_path

def heuristic(a, b):
    """ Calculate the Euclidean distance between two points """
    return math.hypot(b[0] - a[0], b[1] - a[1])

def does_intersect(start, end, vertices):
    """ Check if a line segment intersects with any of the polygon's edges """
    for i in range(len(vertices)):
        p1, p2 = vertices[i], vertices[(i + 1) % len(vertices)]
        if lines_intersect(start, end, p1, p2):
            return True
    return False

def lines_intersect(a, b, c, d):
    """ Check if line segments AB and CD intersect """
    def ccw(A, B, C):
        return (C[1] - A[1]) * (B[0] - A[0]) > (B[1] - A[1]) * (C[0] - A[0])

    return ccw(a, c, d) != ccw(b, c, d) and ccw(a, b, c) != ccw(a, b, d)

def draw_path(path, color="blue"):
    """ Draws the path """
    try:
        T.color(color)
        T.penup()
        T.goto(path[0])
        T.pendown()
        for point in path[1:]:
            T.goto(point)
        T.penup()
    except Exception as e:
        print(f"Error: {e}")
        reset_code()

def reset_code():
    """ Resets the code """
    global vertices
    vertices = []
    T.clearscreen()
    main()

def main():
    global start, end, robot_radius
    # Set the values as provided
    robot_radius = 2
    start = (-200, -200)
    end = (200, 200)
    
    print("Click to define the polygon vertices. Right-click to finish input.")
    
    # Initialize Turtle screen
    screen = T.Screen()
    screen.title("Robot Path Planner")
    screen.setup(width=800, height=600)
    
    T.speed(0)
    T.hideturtle()
    T.penup()
    
    # Show the start and end points immediately
    T.goto(start)
    T.dot(robot_radius * 2 + 10, "green")
    T.write("Start", align="center", font=("Arial", 12, "bold"))
    T.goto(end)
    T.dot(robot_radius * 2 + 10, "red")
    T.write("End", align="center", font=("Arial", 12, "bold"))
    
    # Allow user to click to define polygon vertices
    screen.onscreenclick(click_handler)
    screen.onclick(right_click_handler, btn=3)  # Right click finishes the polygon

    # Add label to top left-hand corner
    T.penup()
    T.goto(-390, 270)  # Adjusted position
    T.write("Blue line = Path Taken", align="left", font=("Arial", 12, "bold"))

    # Wait for the user to finish clicking
    screen.mainloop()

if __name__ == "__main__":
    main()
