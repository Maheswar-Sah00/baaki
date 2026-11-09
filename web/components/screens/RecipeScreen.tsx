"use client";

// Neutral page for the quick exit (/r). Nothing here mentions Baaki, wages or help. On load it
// overwrites the history entry and pushes another neutral one, so Back stays on this page.

import { useEffect } from "react";

export function RecipeScreen() {
  useEffect(() => {
    try {
      window.history.replaceState(null, "", "/r");
      window.history.pushState(null, "", "/r");
      const stay = () => window.history.pushState(null, "", "/r");
      window.addEventListener("popstate", stay);
      return () => window.removeEventListener("popstate", stay);
    } catch {
      return undefined;
    }
  }, []);

  return (
    <main className="recipe">
      <h1>Tomato Pappu</h1>
      <p>Serves 4 · 30 minutes</p>
      <h2>Ingredients</h2>
      <ul>
        <li>1 cup toor dal</li>
        <li>3 tomatoes, chopped</li>
        <li>2 green chillies, slit</li>
        <li>1 onion, sliced</li>
        <li>1/2 tsp turmeric</li>
        <li>Salt to taste</li>
        <li>For tempering: 1 tbsp oil, 1 tsp mustard seeds, 1 tsp cumin, curry leaves, 2 dry red chillies, a pinch of hing</li>
      </ul>
      <h2>Method</h2>
      <ol>
        <li>Wash the dal and pressure cook it with turmeric and 3 cups of water for 3 whistles.</li>
        <li>Cook the onion, chillies and tomatoes in a pan until soft.</li>
        <li>Add the cooked dal and salt, mash lightly, and simmer for 5 minutes.</li>
        <li>Heat oil, add mustard seeds, cumin, red chillies, curry leaves and hing, and pour over the dal.</li>
        <li>Serve hot with rice and ghee.</li>
      </ol>
    </main>
  );
}
