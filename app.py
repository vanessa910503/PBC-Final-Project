from flask import Flask, render_template, request, redirect, url_for, jsonify
import googlemaps
import requests
import json
import os
from collections import defaultdict
from geopy.distance import geodesic

app = Flask(__name__)
api_key = 'AIzaSyDTMROPUW8cwTtiqLSJ94TQGwGYLZJ4No0'  # Replace with your actual API key
gmaps = googlemaps.Client(api_key)

def get_location_from_name(place_name, api_key):
    url = f"https://maps.googleapis.com/maps/api/place/findplacefromtext/json?input={place_name}&inputtype=textquery&fields=geometry,formatted_address,name,rating&language=zh-TW&key={api_key}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        if data['status'] == 'OK':
            location = data['candidates'][0]['geometry']['location']
            address = data['candidates'][0]['formatted_address']
            name = data['candidates'][0].get('name', 'No name available')
            rating = data['candidates'][0].get('rating', 'No rating available')
            return location['lat'], location['lng'], address, name, rating
    return None, None, "Location not found", "No name available", "No rating available"

def calculate_distance(lat1, lng1, lat2, lng2):
    return geodesic((lat1, lng1), (lat2, lng2)).kilometers

@app.route('/')
def index():
    place_types = ['restaurant', 'cafe', 'bar', 'store', 'gym', 'park']
    return render_template('index.html', place_types=place_types)

@app.route('/search_results', methods=['POST'])
def search_results():
    location_name = request.form['location']
    place_types = request.form.getlist('place_type')  # Get list of selected place types
    
    lat, lng, _, _, _ = get_location_from_name(location_name, api_key)
    if lat and lng:
        location = f"{lat},{lng}"
        radius = 1000
        all_places = defaultdict(list)
        
        for place_type in place_types:
            places_result = gmaps.places_nearby(location=location, radius=radius, type=place_type)
            if places_result['status'] == 'OK':
                places = places_result['results']
                for place in places:
                    place_details = gmaps.place(place['place_id'], fields=['name', 'rating', 'geometry'])
                    place['rating'] = place_details['result'].get('rating', 0.0)
                    place['type'] = place_type
                    all_places[place_type].append(place)
        
        for place_list in all_places.values():
            place_list.sort(key=lambda place: place.get('rating', 0.0), reverse=True)
        
        return render_template('selection.html', places=all_places, location_name=location_name, place_types=place_types, location_lat=lat, location_lng=lng)
    
    return render_template('selection.html', places=defaultdict(list), location_name=location_name, place_types=place_types)

@app.route('/results', methods=['POST'])
def results():
    selected_places = request.form.get('selected_places')
    transport_mode = request.form.get('transport_mode')
    location_lat = float(request.form.get('location_lat'))
    location_lng = float(request.form.get('location_lng'))
    selected_places = json.loads(selected_places) if selected_places else []
    
    if not selected_places:
        return render_template('results.html', distances=[])
    
    # Sort places based on distance from the initial location
    sorted_places = sorted(selected_places, key=lambda place: calculate_distance(
        location_lat, location_lng,
        place['geometry']['location']['lat'],
        place['geometry']['location']['lng']
    ))
    
    # Calculate distances and durations
    distances = []
    for i in range(1, len(sorted_places)):
        place1 = sorted_places[i-1]
        place2 = sorted_places[i]
        lat_lng1 = f"{place1['geometry']['location']['lat']},{place1['geometry']['location']['lng']}"
        lat_lng2 = f"{place2['geometry']['location']['lat']},{place2['geometry']['location']['lng']}"
        distance_result = gmaps.distance_matrix(origins=[lat_lng1], destinations=[lat_lng2], mode=transport_mode)
        distance = distance_result['rows'][0]['elements'][0]['distance']['text']
        duration = distance_result['rows'][0]['elements'][0]['duration']['text']
        distances.append({
            'from': place1['name'],
            'to': place2['name'],
            'distance': distance,
            'duration': duration,
            'mode': transport_mode
        })
    
    return render_template('results.html', distances=distances)

if __name__ == '__main__':
    app.run(debug=True)