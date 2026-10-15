/** One pickable chip. `matches` are the exact recipe ingredient names (aisles.yml) it stands
 * for — picking "Pollo" favors recipes using breast, thighs or chicken burgers, keeping
 * the planner's matching exact (no substring/fuzzy guessing) while the UI stays simple. */
export type FavoriteGroup = { label: string; matches: string[] }

// Derived from aisles.yml's "Carne y pescado", "Despensa" (grains/legumes), "Panadería" and the
// fruit items in "Frutería y verdura" — keep these groups in sync whenever that file changes.
// Shared by the first-run onboarding wizard and the Ajustes page, so both stay consistent.
export const FAVORITE_CATEGORIES: { name: string; groups: FavoriteGroup[] }[] = [
  {
    name: "Proteínas",
    groups: [
      { label: "Pollo", matches: ["pechuga de pollo", "contramuslos de pollo", "burger de pollo"] },
      { label: "Ternera", matches: ["carne picada de ternera", "lomo de vacuno añojo"] },
      { label: "Salmón", matches: ["salmón", "salmón ahumado"] },
      { label: "Atún", matches: ["atún en conserva", "ventresca de atún"] },
      { label: "Gambas", matches: ["gambas peladas"] },
      { label: "Jamón", matches: ["jamón serrano"] },
      { label: "Huevos", matches: ["huevos"] },
    ],
  },
  {
    name: "Hidratos",
    groups: [
      { label: "Arroz", matches: ["arroz", "arroz cocido", "arroz para risotto"] },
      { label: "Pasta", matches: ["pasta pequeña", "fideos de arroz"] },
      { label: "Patata", matches: ["patata", "boniato"] },
      { label: "Avena", matches: ["copos de avena"] },
      { label: "Pan", matches: ["pan integral"] },
      { label: "Garbanzos", matches: ["garbanzos cocidos"] },
      { label: "Lentejas", matches: ["lentejas cocidas"] },
      { label: "Frijoles", matches: ["frijoles negros cocidos", "frijoles rojos cocidos"] },
    ],
  },
  {
    name: "Verduras",
    groups: [
      { label: "Aguacate", matches: ["aguacate"] },
      { label: "Brócoli", matches: ["brócoli"] },
      { label: "Calabacín", matches: ["calabacín"] },
      { label: "Champiñones", matches: ["champiñones"] },
      { label: "Espinacas", matches: ["espinacas frescas"] },
      { label: "Guisantes", matches: ["guisantes congelados"] },
      { label: "Judías verdes", matches: ["judías verdes"] },
      { label: "Pimiento", matches: ["pimiento rojo", "pimiento verde"] },
      { label: "Tomate", matches: ["tomate", "tomate pera", "tomate triturado"] },
      { label: "Zanahoria", matches: ["zanahoria"] },
    ],
  },
  {
    name: "Frutas",
    groups: [
      { label: "Manzana", matches: ["manzana"] },
      { label: "Plátano", matches: ["plátano"] },
      { label: "Lima", matches: ["lima"] },
      { label: "Limón", matches: ["limón"] },
    ],
  },
]
