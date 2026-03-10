import math

def calculate_distance(route_points):
    total_distance = 0

    for i in range(len(route_points) - 1):
        lat1 = route_points[i]['lat']
        lon1 = route_points[i]['lng']
        lat2 = route_points[i+1]['lat']
        lon2 = route_points[i+1]['lng']

        R = 6371  # Earth radius in KM

        dLat = math.radians(lat2 - lat1)
        dLon = math.radians(lon2 - lon1)

        a = (
            math.sin(dLat/2) ** 2 +
            math.cos(math.radians(lat1)) *
            math.cos(math.radians(lat2)) *
            math.sin(dLon/2) ** 2
        )

        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        distance = R * c

        total_distance += distance

    return round(total_distance, 2)