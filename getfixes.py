# Copyright 2024 Robert Mason
# 
# Permission to use, copy, modify, and/or distribute this software for any 
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
# 
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
# ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
# WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
# ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF OR
# IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

# Get fixes from stdin and and output a tab-delimited file
# with each fix's lat/long (or blank if not known)
#
# This depends on geopy (deb: python3-geopy)
# and BeautifulSoup (deb: python3-bs4)
# 
# It scrapes the lat/longs from [AirNav](https://www.airnav.com/)

from urllib import request
from bs4 import BeautifulSoup as bs
import re
import geopy
import geopy.distance

location_regex = re.compile('Location')
arpt_location_regex = re.compile('Lat')
latlong_regex = re.compile(r'(\d+)-(\d+)-(\d+.\d+)([NSEW])')
var_regex = re.compile(r'(\d?\d)([EW])')
offset_regex = re.compile(r'([A-Z][A-Z][A-Z])(\d\d\d)(\d\d\d)')
airnav = 'https://www.airnav.com/'

def get_latlong(s):
    match = latlong_regex.match(s)
    degrees = int(match.group(1))
    minutes = int(match.group(2)) + (float(match.group(3))/60.)
    return (match.group(4), degrees, minutes)

def get_point(lat, long):
    point_str = ' '.join(
        '{} {}m {}s {}'.format(*latlong_regex.match(s).group(1, 2, 3, 4))
        for s in [lat, long])
    return geopy.point.Point.from_string(point_str)

def deg_to_degmin(val):
    degs = int(val)
    mins = 60 * (val - degs)
    return (degs, mins)

def degmin_to_str(degs, mins):
    return ('{:02d}'.format(degs) + ' '
         + '{:.2f}'.format(mins).zfill(5))

def point_to_strs(point):
    lat, long, _ = point
    # Don't care about N/S E/W
    lat = abs(lat)
    long= abs(long)
    return [degmin_to_str(*deg_to_degmin(x)) for x in [lat, long]]

def var_from_str(s):
    # We'll call Easterly variation positive
    var, direction = var_regex.match(s).group(1, 2)
    mul = 1
    if direction == 'W':
        mul = -1
    return mul * int(var)

def get_fix(fix):
    base = airnav + 'airspace/fix/'
    with request.urlopen(base + fix) as resp:
        html = resp.read()
        soup = bs(html, "html.parser")
        elem = soup.find('th', string=location_regex)
        loc_str = elem.next_sibling.string
        return get_point(*loc_str.split())

def get_navaid(navaid):
    base = airnav + 'cgi-bin/navaid-info?a='
    with request.urlopen(base + navaid) as resp:
        html = resp.read()
        soup = bs(html, "html.parser")
        elem = soup.find('h3', string='Location')
        loc = elem.find_next_sibling('pre').string.split()
        point = get_point(loc[1], loc[3])
        var = var_from_str(loc[9])
        return (point, var)

def get_airport(arpt):
    base = airnav + 'airport/'
    with request.urlopen(base + arpt) as resp:
        html = resp.read()
        soup = bs(html, 'html.parser')
        elem = soup.find('td', string=arpt_location_regex)
        loc_str = elem.next_sibling.next_element
        return get_point(*loc_str.split())

import sys

for line in sys.stdin:
    identifier = line.strip()
    loc = None
    try:
        if len(identifier) == 3:
            loc, _ = get_navaid(identifier)
        elif len(identifier) == 4:
            loc = get_airport(identifier)
        elif len(identifier) == 5:
            loc = get_fix(identifier)
        elif len(identifier) == 9:
            match = offset_regex.match(identifier)
            navaid, radial, dist = match.group(1, 2, 3)
            radial = int(radial)
            dist = int(dist)
            navaid, var = get_navaid(navaid)
            bearing = radial + var
            if bearing >= 360:
                bearing = bearing - 360
            loc = (geopy.distance.distance(kilometers=1.852*dist)
                .destination(navaid, bearing=bearing))
    except e:
        pass
    if loc is not None:
        lat, long = point_to_strs(loc)
        print('{}\t{}\t{}'.format(identifier, lat, long))
    else:
        print(identifier)

