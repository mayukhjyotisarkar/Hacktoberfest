export interface LocationFeatureResult {
  displayName: string;
  lat?: string;
  lon?: string;
  category?: string;
  type?: string;
  /** Broad place classification returned by Nominatim, not verified on-site features. */
  features: string[];
  isOSMPlaceMatched: boolean;
}

/** Looks up a user-entered place with Nominatim; it does not inspect nearby objects. */
export async function fetchOSMFeatures(placeName: string): Promise<LocationFeatureResult> {
  const fallback = (displayName: string): LocationFeatureResult => ({
    displayName,
    features: [],
    isOSMPlaceMatched: false
  });

  if (!placeName || placeName.trim().length < 2) {
    return fallback(placeName);
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 4000);

  try {
    const searchUrl = `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(placeName)}&addressdetails=1&limit=1`;
    const response = await fetch(searchUrl, {
      headers: { Accept: 'application/json' },
      signal: controller.signal
    });

    if (!response.ok) {
      throw new Error(`OSM Nominatim returned HTTP ${response.status}`);
    }

    const data = await response.json();
    const place = Array.isArray(data) ? data[0] : undefined;
    if (!place) return fallback(placeName);

    const category = place.category || place.class;
    const type = place.type;
    const mappedPlaceType = typeof type === 'string' && type.trim()
      ? `Mapped place type: ${type.replaceAll('_', ' ')}`
      : typeof category === 'string' && category.trim()
        ? `Mapped place category: ${category}`
        : '';

    return {
      displayName: place.display_name || placeName,
      lat: place.lat,
      lon: place.lon,
      category,
      type,
      features: mappedPlaceType ? [mappedPlaceType] : [],
      isOSMPlaceMatched: true
    };
  } catch (error) {
    console.warn('OSM place lookup fallback:', error);
    return fallback(placeName);
  } finally {
    clearTimeout(timeoutId);
  }
}
