import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../api/client";

type Tab = "planner" | "recipes" | "shopping";

interface Recipe {
  id: string;
  title: string;
  ingredients_raw?: string;
  steps_raw?: string;
  prep_time_min?: number;
  cook_time_min?: number;
  servings?: number;
  dietary_tag_ids: string[];
  dietary_tags: { id: string; name: string; color_hex: string }[];
}

interface MealPlan {
  id: string;
  meal_type: string;
  date: string;
  recipe_id?: string;
  title: string;
  notes?: string;
  recipe?: { id: string; title: string };
}

interface ShoppingItem {
  id: string;
  item: string;
  quantity?: string;
  is_checked: boolean;
  is_persistent: boolean;
  source: string;
  week_start_date: string;
}

export default function MealsPage() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<Tab>("planner");
  const [weekStart, setWeekStart] = useState(() => {
    const today = new Date();
    const monday = new Date(today);
    monday.setDate(today.getDate() - today.getDay() + 1);
    return monday.toISOString().split("T")[0];
  });

  const queryClient = useQueryClient();

  // Queries
  const { data: _dietaryTags = [] } = useQuery({
    queryKey: ["meals", "dietary-tags"],
    queryFn: () => api.get('/meals/dietary-tags').then(r => r.data),
  });

  const { data: recipes = [] } = useQuery({
    queryKey: ["meals", "recipes"],
    queryFn: () => api.get('/meals/recipes').then(r => r.data),
  });

  const { data: weekPlans } = useQuery({
    queryKey: ["meals", "plans", weekStart],
    queryFn: () => api.get('/meals/plans', { params: { week_start: weekStart } }).then(r => r.data),
  });

  const { data: shoppingItems = [] } = useQuery({
    queryKey: ["meals", "shopping", weekStart],
    queryFn: () => api.get('/meals/shopping-list', { params: { week_start: weekStart } }).then(r => r.data),
  });

  // Mutations
  const createRecipeMutation = useMutation({
    mutationFn: (data: { title: string; content_text: string; ingredients_raw?: string; steps_raw?: string; dietary_tag_ids: string[] }) =>
      api.post('/meals/recipes', data).then(r => r.data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["meals", "recipes"] }),
  });

  const createMealPlanMutation = useMutation({
    mutationFn: (data: { meal_type: string; date: string; recipe_id?: string; title: string; notes?: string }) =>
      api.post('/meals/plans', data).then(r => r.data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["meals", "plans"] }),
  });

  const [shoppingItemForm, setShoppingItemForm] = useState({ item: "", quantity: "" })
  const [showAddItemForm, setShowAddItemForm] = useState(false)
  const [addItemError, setAddItemError] = useState("")

  const addShoppingItemMutation = useMutation({
    mutationFn: (data: { item: string; quantity?: string }) =>
      api.post('/meals/shopping-list', data).then(r => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["meals", "shopping"] });
      setShoppingItemForm({ item: "", quantity: "" });
      setShowAddItemForm(false);
      setAddItemError("");
    },
    onError: (err: any) => {
      setAddItemError(err.response?.data?.detail || "Failed to add item");
    },
  })

  const updateShoppingItemMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<ShoppingItem> }) =>
      api.patch(`/meals/shopping-list/${id}`, data).then(r => r.data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["meals", "shopping"] }),
  });

  const deleteMealPlanMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/meals/plans/${id}`).then(r => r.data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["meals", "plans"] }),
  });

  // Week navigation helpers
  const changeWeek = (delta: number) => {
    const d = new Date(weekStart);
    d.setDate(d.getDate() + delta * 7);
    setWeekStart(d.toISOString().split("T")[0]);
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr + "T00:00:00").toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });
  };

  const days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  const mealTypes = ["breakfast", "lunch", "dinner", "snack"];

  // Get meal for a specific date+type
  const getMeal = (date: string, mealType: string) => {
    return weekPlans?.meals?.find((m: MealPlan) => m.date === date && m.meal_type === mealType);
  };

  // Generate dates for the week
  const weekDates = Array.from({ length: 7 }, (_, i) => {
    const d = new Date(weekStart + "T00:00:00");
    d.setDate(d.getDate() + i);
    return d.toISOString().split("T")[0];
  });

  return (
    <div className="space-y-6">
      {/* Header with week navigation */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate("/")}
            className="px-3 py-2 rounded-lg bg-slate-700 text-white hover:bg-slate-600 transition"
          >
            ←
          </button>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            🍽️ Meal Planning
          </h1>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => changeWeek(-1)}
            className="px-3 py-2 rounded-lg bg-slate-700 text-white hover:bg-slate-600 transition"
          >
            ←
          </button>
          <span className="text-white font-medium">
            Week of {formatDate(weekStart)}
          </span>
          <button
            onClick={() => changeWeek(1)}
            className="px-3 py-2 rounded-lg bg-slate-700 text-white hover:bg-slate-600 transition"
          >
            →
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2">
        {([
          { key: "planner", label: "Planner", icon: "📅" },
          { key: "recipes", label: "Recipes", icon: "📖" },
          { key: "shopping", label: "Shopping List", icon: "🛒" },
        ] as const).map(tab => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-4 py-2 rounded-lg transition ${
              activeTab === tab.key
                ? "bg-emerald-600 text-white"
                : "bg-slate-700 text-slate-300 hover:bg-slate-600"
            }`}
          >
            {tab.icon} {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === "planner" && (
        <div className="bg-slate-800/50 backdrop-blur rounded-xl p-4 border border-slate-700 overflow-x-auto">
          <table className="w-full min-w-[800px]">
            <thead>
              <tr>
                <th className="p-3 text-left text-slate-400 font-medium">Meal Type</th>
                {weekDates.map((date, i) => (
                  <th key={date} className="p-3 text-center text-slate-300 font-medium">
                    <div>{days[i]}</div>
                    <div className="text-xs text-slate-500">{formatDate(date).split(",")[1]?.trim()}</div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {mealTypes.map(mealType => (
                <tr key={mealType} className="border-t border-slate-700">
                  <td className="p-3 font-medium text-white capitalize">{mealType}</td>
                  {weekDates.map(date => {
                    const meal = getMeal(date, mealType);
                    return (
                      <td key={date} className="p-2 text-center">
                        {meal ? (
                          <div className="bg-slate-700/50 rounded-lg p-2">
                            <p className="text-white text-sm truncate">{meal.title}</p>
                            {meal.recipe && (
                              <p className="text-emerald-400 text-xs mt-1">{meal.recipe.title}</p>
                            )}
                            <button
                              onClick={() => {
                                if (confirm("Remove this meal?")) {
                                  deleteMealPlanMutation.mutate(meal.id);
                                }
                              }}
                              className="text-red-400 text-xs mt-1 hover:text-red-300"
                            >
                              ✕
                            </button>
                          </div>
                        ) : (
                          <button
                            onClick={() => {
                              const title = prompt(`Add ${mealType} for ${formatDate(date)}:`);
                              if (title) {
                                createMealPlanMutation.mutate({ meal_type: mealType, date, title });
                              }
                            }}
                            className="w-full p-2 rounded-lg border border-dashed border-slate-600 text-slate-500 hover:border-emerald-500 hover:text-emerald-400 transition text-sm"
                          >
                            + Add
                          </button>
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {activeTab === "recipes" && (
        <div className="space-y-4">
          <div className="flex gap-3">
            <input
              type="text"
              placeholder="Search recipes..."
              className="flex-1 px-4 py-2 rounded-lg bg-slate-700 text-white border border-slate-600 focus:border-emerald-500 focus:outline-none"
            />
            <button
              onClick={() => {
                const text = prompt("Paste recipe text:");
                if (text) {
                  const title = prompt("Recipe title:", text.split("\n")[0]?.trim() || "Untitled");
                  if (title) {
                    createRecipeMutation.mutate({
                      title,
                      content_text: text,
                      dietary_tag_ids: [],
                    });
                  }
                }
              }}
              className="px-4 py-2 rounded-lg bg-emerald-600 text-white hover:bg-emerald-500 transition"
            >
              + Add Recipe
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {recipes.map((recipe: Recipe) => (
              <div
                key={recipe.id}
                className="bg-slate-800/50 backdrop-blur rounded-xl p-4 border border-slate-700 hover:border-emerald-500/30 transition cursor-pointer"
              >
                <h3 className="text-white font-medium mb-2">{recipe.title}</h3>
                <div className="flex gap-2 flex-wrap mb-3">
                  {recipe.dietary_tags.map((tag: { id: string; name: string; color_hex: string }) => (
                    <span
                      key={tag.id}
                      className="px-2 py-0.5 rounded-full text-xs text-white"
                      style={{ backgroundColor: tag.color_hex + "40", color: tag.color_hex }}
                    >
                      {tag.name}
                    </span>
                  ))}
                </div>
                <div className="text-slate-400 text-sm space-y-1">
                  {recipe.prep_time_min && <p>⏱ Prep: {recipe.prep_time_min}min</p>}
                  {recipe.cook_time_min && <p>🔥 Cook: {recipe.cook_time_min}min</p>}
                  {recipe.servings && <p>🍽 Serves: {recipe.servings}</p>}
                  {recipe.ingredients_raw && (
                    <p>📝 {recipe.ingredients_raw.split("\n").filter(Boolean).length} ingredients</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {activeTab === "shopping" && (
        <div className="space-y-4">
          <div className="flex gap-3">
            <button
              onClick={() => {
                if (confirm("Regenerate shopping list from meal plans? This will remove all non-persistent items.")) {
                  api.post('/meals/shopping-list/regenerate').then(() => {
                    queryClient.invalidateQueries({ queryKey: ["meals", "shopping"] });
                  });
                }
              }}
              className="px-4 py-2 rounded-lg bg-emerald-600 text-white hover:bg-emerald-500 transition"
            >
              🔄 Regenerate
            </button>
            <button
              onClick={() => setShowAddItemForm(true)}
              className="px-4 py-2 rounded-lg bg-slate-700 text-white hover:bg-slate-600 transition"
            >
              + Add Item
            </button>
          </div>

          {showAddItemForm && (
            <div className="p-4 rounded-xl bg-slate-800/80 border border-slate-600">
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  if (!shoppingItemForm.item.trim()) return;
                  addShoppingItemMutation.mutate({
                    item: shoppingItemForm.item.trim(),
                    quantity: shoppingItemForm.quantity.trim() || undefined,
                  });
                }}
                className="flex gap-3"
              >
                <input
                  type="text"
                  value={shoppingItemForm.item}
                  onChange={(e) => setShoppingItemForm({ ...shoppingItemForm, item: e.target.value })}
                  placeholder="Item name"
                  className="flex-1 px-3 py-2 rounded-lg bg-slate-700 border border-slate-600 text-white focus:outline-none focus:ring-2 focus:ring-emerald-500"
                  required
                  autoFocus
                />
                <input
                  type="text"
                  value={shoppingItemForm.quantity}
                  onChange={(e) => setShoppingItemForm({ ...shoppingItemForm, quantity: e.target.value })}
                  placeholder="Qty (optional)"
                  className="w-32 px-3 py-2 rounded-lg bg-slate-700 border border-slate-600 text-white focus:outline-none focus:ring-2 focus:ring-emerald-500"
                />
                <button
                  type="submit"
                  disabled={addShoppingItemMutation.isPending}
                  className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:bg-emerald-400 text-white transition"
                >
                  Add
                </button>
                <button
                  type="button"
                  onClick={() => { setShowAddItemForm(false); setAddItemError(""); }}
                  className="px-4 py-2 rounded-lg bg-slate-600 hover:bg-slate-500 text-white transition"
                >
                  Cancel
                </button>
              </form>
              {addItemError && <p className="text-red-400 text-sm mt-2">{addItemError}</p>}
            </div>
          )}

          <div className="bg-slate-800/50 backdrop-blur rounded-xl border border-slate-700 divide-y divide-slate-700">
            {shoppingItems.length === 0 ? (
              <div className="p-8 text-center text-slate-400">
                <p className="text-lg">No items yet</p>
                <p className="text-sm mt-1">Add items manually or regenerate from meal plans</p>
              </div>
            ) : (
              shoppingItems.map((item: ShoppingItem) => (
                <div key={item.id} className="flex items-center gap-3 p-4 hover:bg-slate-700/30 transition">
                  <button
                    onClick={() => updateShoppingItemMutation.mutate({
                      id: item.id,
                      data: { is_checked: !item.is_checked },
                    })}
                    className={`w-5 h-5 rounded border-2 flex items-center justify-center transition ${
                      item.is_checked
                        ? "bg-emerald-500 border-emerald-500"
                        : "border-slate-500 hover:border-emerald-400"
                    }`}
                  >
                    {item.is_checked && <span className="text-white text-xs">✓</span>}
                  </button>
                  <div className="flex-1">
                    <p className={`text-white ${item.is_checked ? "line-through text-slate-400" : ""}`}>
                      {item.item}
                    </p>
                    {item.quantity && <p className="text-slate-400 text-sm">{item.quantity}</p>}
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => {
                        const newPersistent = !item.is_persistent;
                        updateShoppingItemMutation.mutate({ id: item.id, data: { is_persistent: newPersistent } });
                      }}
                      className={`px-2 py-1 rounded text-xs transition ${
                        item.is_persistent
                          ? "bg-amber-500/20 text-amber-400"
                          : "bg-slate-700 text-slate-400 hover:text-amber-400"
                      }`}
                      title="Toggle persistent (carries over week to week)"
                    >
                      {item.is_persistent ? "⭐ Persistent" : "Persistent"}
                    </button>
                    <button
                      onClick={() => {
                        if (confirm(`Delete "${item.item}"?`)) {
                          api.delete(`/meals/shopping-list/${item.id}`).then(() => {
                            queryClient.invalidateQueries({ queryKey: ["meals", "shopping"] });
                          });
                        }
                      }}
                      className="text-slate-500 hover:text-red-400 transition"
                    >
                      ✕
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>

          <div className="text-slate-400 text-sm">
            {shoppingItems.length} items · {shoppingItems.filter((i: ShoppingItem) => i.is_checked).length} checked · {shoppingItems.filter((i: ShoppingItem) => !i.is_checked).length} remaining
          </div>
        </div>
      )}
    </div>
  );
}
