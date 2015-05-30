from django.shortcuts import render
from django.http import HttpResponse, HttpResponseRedirect
from django.http import JsonResponse
from django.views.decorators.cache import cache_page

from silk.profiling.profiler import silk_profile

import datetime
import re
import googlemaps
import traceback
import dateutil.parser
import gpxpy
import gpxpy.gpx

from biketour.settings import GOOGLE_MAPS_API_KEY
from .models import Point
from .forms import UploadFileForm

def log(request):
    point = Point()

    point.time = dateutil.parser.parse(request.GET['time'])

    point.lat = float(request.GET['lat'])
    point.lon = float(request.GET['lon'])

    point.speed = float(request.GET['speed'])
    point.native_altitude = float(request.GET['altitude'])
    point.accuracy = float(request.GET['accuracy'])
    point.battery = float(request.GET['battery'])
    point.satellites = int(request.GET['satellites'])
    point.direction = float(request.GET['direction'])
    point.provider = request.GET['provider']

    try:
        gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)

        result = gmaps.elevation((lat, lon))[0]
        resolution = result['resolution']
        point.google_altitude = result['elevation']
    except Exception:
        point.google_altitude = 0

    point.save()

    return HttpResponse(status=200)


def extract_point(point):
    return  {
        'type': 'Feature',
        'properties': {
            'time': point.time,
            'accuracy': point.accuracy,
            'speed': point.speed,
            'battery': point.battery,
            'provider': point.provider,
            'altitude': point.native_altitude,
            'marker-symbol': 'bicycle',
            'marker-color': '#2c3e50',
            'marker-size': 'large',
        },
        'geometry': {
            'type': 'Point',
            'coordinates': [point.lon, point.lat],
        }
    }


def upload_gpx(request):

    def create_point(parsed_point):
        point = Point()

        point.time = parsed_point.time
        if not point.time:
            point.time = datetime.datetime.now()

        point.native_altitude = parsed_point.elevation
        point.lat = parsed_point.latitude
        point.lon = parsed_point.longitude

        point.save()
        

    def handle_uploaded_file(gpx_file):
        content = gpx_file.read().decode("utf-8")
        gpx = gpxpy.parse(content)
        for track in gpx.tracks:
            for segment in track.segments:
                for point in segment.points:
                    create_point(point)

    if request.method == 'POST':
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            handle_uploaded_file(request.FILES['file'])
            return HttpResponseRedirect('/')
    else:
        form = UploadFileForm()
    return render(request, 'gps/upload.html', {'form': form})


@cache_page(30)
def track(request):

    @silk_profile()
    def extract_line(points):
        coords = [[p['lon'], p['lat']] for p in points]
        return  {
            'type': 'Feature',
            'geometry': {
                'type': 'LineString',
                'coordinates': coords,
            },
            'properties': {
                'stroke': '#2c3e50',
                'stroke-width': 4
            }
        }


    points = Point.objects.all().order_by('time').values('lon', 'lat')

    return JsonResponse({
        'type': 'FeatureCollection',
        'features': [
            extract_line(points),
        ]
    }, safe=False)


def map(request):
    return render(request, 'gps/map.html')


def current_position(request):
    current_pos = Point.objects.all().order_by('-time')[0]
    return JsonResponse({
        'type': 'FeatureCollection',
        'features': [
                extract_point(current_pos)
        ]
    }, safe=False)
