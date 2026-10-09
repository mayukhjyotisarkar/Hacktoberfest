import type { MissionData, MissionRequest } from '../types';

export const HAND_WRITTEN_MISSIONS: Record<string, MissionData[]> = {
  mystery: [
    {
      title: "The Case of the Whispering Archway",
      story_hook: "Local legends speak of an unspoken code left behind by ancient city surveyors. A secret signal was hidden near public structures, waiting for observant eyes.",
      destination_suggestion: "Walk towards the central arch, main entrance pillar, or historical marker near {landmark}.",
      clue: "Seek where old stone or brass meets shadow. Look for an inscription, etched date, or recurring geometric pattern.",
      objective: "Spot a number or carved symbol near the architectural base and whisper its meaning to your squad before moving on.",
      story_ending: "With the symbol deciphered, the ancient surveyor code is deciphered! Your squad has uncovered the hidden history of the realm.",
      badge_name: "Shadow Investigator"
    },
    {
      title: "The Cipher of the Forgotten Lamp",
      story_hook: "An enigmatic courier once used public streetlamps to leave hidden markings for allies in plain sight.",
      destination_suggestion: "Stroll toward the perimeter or main walkway of {landmark} where lanterns or light posts stand.",
      clue: "Find the base of the nearest ornamental post or light fixture. Notice what material or number tag is attached.",
      objective: "Count how many paces separate the light post from the nearest tree line or bench.",
      story_ending: "The cipher distance checks out! The path of the forgotten courier remains intact thanks to your squad's keen eyes.",
      badge_name: "Streetlight Sentinel"
    }
  ],
  nature: [
    {
      title: "The Canopy Guardian's Secret",
      story_hook: "The urban wilderness conceals ancient guardians—the tallest trees and oldest stone planters guarding life in the city.",
      destination_suggestion: "Head toward the greenest cluster, flower bed, or shaded tree grove at {landmark}.",
      clue: "Find the tree with the widest leaf canopy or the oldest bark texture nearby.",
      objective: "Locate three distinct leaf shapes or bark patterns without disturbing any vegetation or touching wildlife.",
      story_ending: "The Canopy Guardian recognizes your respect for the green realm. Nature's quiet wisdom shines upon your squad!",
      badge_name: "Leafweaver Scout"
    },
    {
      title: "The Way of the Wild Horizon",
      story_hook: "Breezes carry tales across open sky, but only those who stop and observe the horizon can read the weather runes.",
      destination_suggestion: "Walk to the highest viewpoint, open courtyard, or grassy mound near {landmark}.",
      clue: "Position your squad facing North (or toward the sun's direction) and look up at cloud formations or flying birds.",
      objective: "Identify the dominant direction of the wind using moving leaves, flags, or cloud drifts.",
      story_ending: "You have decoded the wind's message! The sky spirits bless your expedition with clear trails ahead.",
      badge_name: "Windward Pathfinder"
    }
  ],
  silly: [
    {
      title: "Operation: Pigeon Protocol",
      story_hook: "Secret agent pigeons have taken over the perimeter. They are watching every move, disguised as harmless everyday birds!",
      destination_suggestion: "Advance stealthily toward the busiest open plaza or bench area near {landmark}.",
      clue: "Look for anything shaped like a feather, or any suspicious bird perched like a tiny boss.",
      objective: "Strike a synchronized secret-agent pose near a bench for 5 seconds without laughing.",
      story_ending: "Agent Pigeon nods in respect! Your covert operation was a resounding success. High-fives all around!",
      badge_name: "Feathered Operative"
    },
    {
      title: "The Quest for the Legendary Funny Bench",
      story_hook: "Prophecy foretells of a public seating area bestowed with magical energy. Sitting upon it grants instant wisdom and mild giggles.",
      destination_suggestion: "Navigate your squad toward the most inviting bench or seating area around {landmark}.",
      clue: "Find a bench that looks like it has seen the most dramatic conversations in town.",
      objective: "Each squad member must deliver their best 5-second dramatic movie monologue while seated on the bench.",
      story_ending: "The Legendary Bench approves! An aura of pure joy fills the squad. You are officially certified legends!",
      badge_name: "Bench Royalty"
    }
  ],
  fantasy: [
    {
      title: "The Keystone of the Sunken Guild",
      story_hook: "A portal to the Eldermoss Realm remains dormant beneath modern stone. Only a squad of brave adventurers can awaken its resonance.",
      destination_suggestion: "Journey toward the sturdy stone foundation, steps, or fountain edge near {landmark}.",
      clue: "Search for a cornerstone or stone seam where two different building materials meet.",
      objective: "Form a circle around the cornerstone and recite your squad's battle cry in a whisper.",
      story_ending: "A golden pulse reverberates through the ground! The portal glows faintly as your squad earns entry into the Guild of Wandering Legends.",
      badge_name: "Eldermoss Wayfinder"
    },
    {
      title: "The Beacon of the Star-Gazer",
      story_hook: "In ages past, stargazers planted hidden terrestrial markers aligned with celestial constellations.",
      destination_suggestion: "Walk toward an open space with a clear view of the sky or a central monument near {landmark}.",
      clue: "Look for a circular paving stone, brass plaque, or compass-like design on the ground.",
      objective: "Align your squad members to point toward the four cardinal directions (N, S, E, W) simultaneously.",
      story_ending: "The celestial beacon aligns! Stellar energy charges your spirit, banishing desk fatigue forever!",
      badge_name: "Astral Navigator"
    }
  ]
};

export function getFallbackMission(request: MissionRequest): MissionData {
  const vibeMissions = HAND_WRITTEN_MISSIONS[request.vibe] || HAND_WRITTEN_MISSIONS.nature;
  const index = Math.abs(request.landmark.length) % vibeMissions.length;
  const template = vibeMissions[index];

  const destination = template.destination_suggestion.replace('{landmark}', request.landmark || 'your nearby public spot');

  return {
    ...template,
    destination_suggestion: destination,
    vibe: request.vibe,
    landmark: request.landmark,
    id: `mission-${Date.now()}`,
    createdAt: new Date().toISOString()
  };
}
