import math
from ortools.sat.python import cp_model

coords = [
    (16.47, 96.10), (16.47, 94.44), (20.09, 92.54), (22.39, 93.37),
    (25.23, 97.24), (22.00, 96.00), (20.47, 97.00), (17.20, 96.29),
    (16.30, 97.38), (14.05, 98.12), (16.53, 99.32), (21.52, 95.59),
    (19.41, 97.13), (20.09, 94.55)
]

def to_rad_tsplib(x):
    PI = 3.141592
    deg = int(x)
    minutes = x - deg
    return PI * (deg + 5.0 * minutes / 3.0) / 180.0

RRR = 6378.388
n = len(coords)

# Test 1: (lat, lon) = (c[0], c[1])
# Test 2: (lat, lon) = (c[1], c[0])
for swap in [False, True]:
    mat = [[0]*n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i != j:
                if not swap:
                    lat1, lon1 = to_rad_tsplib(coords[i][0]), to_rad_tsplib(coords[i][1])
                    lat2, lon2 = to_rad_tsplib(coords[j][0]), to_rad_tsplib(coords[j][1])
                else:
                    lat1, lon1 = to_rad_tsplib(coords[i][1]), to_rad_tsplib(coords[i][0])
                    lat2, lon2 = to_rad_tsplib(coords[j][1]), to_rad_tsplib(coords[j][0])
                q1 = math.cos(lon1 - lon2)
                q2 = math.cos(lat1 - lat2)
                q3 = math.cos(lat1 + lat2)
                d = RRR * math.acos(0.5 * ((1.0 + q1) * q2 - (1.0 - q1) * q3)) + 1.0
                mat[i][j] = int(d)

    model = cp_model.CpModel()
    arcs = []
    lit = {}
    for i in range(n):
        for j in range(n):
            if i != j:
                lit[i, j] = model.NewBoolVar(f"x_{i}_{j}")
                arcs.append((i, j, lit[i, j]))
    model.AddCircuit(arcs)
    model.Minimize(sum(mat[i][j] * lit[i, j] for i in range(n) for j in range(n) if i != j))
    solver = cp_model.CpSolver()
    status = solver.Solve(model)
    print(f"Swap={swap}, CP-SAT Objective: {solver.ObjectiveValue()}")
