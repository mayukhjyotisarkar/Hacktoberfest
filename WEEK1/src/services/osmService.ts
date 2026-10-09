export interface LocationFeatureResult {
  displayName: string;
  lat?: string;
  lon?: string;
  category?: string;
  type?: string;
  features: string[];
  isOSMConfirmed: boolean;
}

/**
 * Queries OpenStreetMap Nominatim & Overpass APIs to find real-world physical features
 * associated with a user-provided public place string.
 */
export async function fetchOSMFeatures(placeName: string): Promise<LocationFeatureResult> {
  if (!placeName || placeName.trim().length < 2) {
    return {
      displayName: placeName,
      features: ['public pathway', 'seating or ledge', 'trees or green plants'],
      isOSMConfirmed: false
    };
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 4000); // 4-second timeout for snappy UI

  try {
    const searchUrl = `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(placeName)}&extratags=1&addressdetails=1&limit=1`;
    
    const response = await fetch(searchUrl, {
      headers: {
        'Accept': 'application/json',
        'User-Agent': 'RaidOutside-CoOpApp/1.0'
      },
      signal: controller.signal
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      throw new Error(`OSM Nominatim returned HTTP ${response.status}`);
    }

    const data = await response.json();

    if (!data || data.length === 0) {
      // Fallback features if place name was generic or not found in OSM database
      return {
        displayName: placeName,
        features: ['public pathway', 'seating area or bench', 'greenery or shade trees', 'architectural wall or post'],
        isOSMConfirmed: false
      };
    }

    const place = data[0];
    const extractedFeatures: string[] = [];

    // Map OSM category & type tags to readable real-world objects
    const cat = place.category || place.class;
    const type = place.type;
    const address = place.address || {};

    if (cat === 'leisure' || type === 'park' || type === 'garden' || type === 'playground') {
      extractedFeatures.push('park lawn & foliage', 'benches & seating', 'shade trees');
    }
    if (cat === 'amenity' && (type === 'fountain' || type === 'drinking_water')) {
      extractedFeatures.push('water fountain or basin');
    }
    if (cat === 'historic' || type === 'monument' || type === 'memorial' || type === 'statue') {
      extractedFeatures.push('historic plaque or stone monument');
    }
    if (cat === 'building' || address.building || type === 'library' || type === 'townhall') {
      extractedFeatures.push('building pillars & facade', 'stone entrance steps');
    }

    // Default physical elements present in open public places
    extractedFeatures.push('public walkway', 'directional signs or light posts');

    // Deduplicate
    const uniqueFeatures = Array.from(new Set(extractedFeatures));

    return {
      displayName: place.display_name || placeName,
      lat: place.lat,
      lon: place.lon,
      category: cat,
      type: type,
      features: uniqueFeatures,
      isOSMConfirmed: true
    };
  } catch (error) {
    clearTimeout(timeoutId);
    console.warn('OSM Feature lookup fallback:', error);

    return {
      displayName: placeName,
      features: ['public walkway', 'seating area', 'foliage or trees', 'signpost or lantern'],
      isOSMConfirmed: false
    };
  }
}
