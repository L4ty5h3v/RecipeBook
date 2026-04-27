const state = {
  meta: null,
  products: [],
  dishes: [],
};

const toast = document.getElementById("toast");
const modal = document.getElementById("details-modal");
const modalTitle = document.getElementById("modal-title");
const modalContent = document.getElementById("modal-content");
const dishNutritionFields = ["dish-calories", "dish-protein", "dish-fat", "dish-carbs"];

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  if (response.status === 204) {
    return null;
  }

  const data = await response.json();
  if (!response.ok) {
    const error = new Error(data.error || "Ошибка запроса");
    error.payload = data;
    throw error;
  }
  return data;
}

function showToast(message) {
  toast.textContent = message;
  toast.classList.remove("hidden");
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => toast.classList.add("hidden"), 3200);
}

function renderGallery(photos, alt) {
  if (!photos?.length) {
    return '<div class="card-image placeholder">Без фото</div>';
  }
  return `<div class="card-gallery">${photos
    .map(
      (src, index) =>
        `<img class="card-image" src="${src}" alt="${alt} ${index + 1}" />`,
    )
    .join("")}</div>`;
}

function openModal(title, content) {
  modalTitle.textContent = title;
  modalContent.innerHTML = content;
  modal.classList.remove("hidden");
}

function closeModal() {
  modal.classList.add("hidden");
}

function markDishNutritionAsAuto() {
  dishNutritionFields.forEach((id) => {
    const input = document.getElementById(id);
    input.dataset.manual = "false";
  });
}

function applySuggestedValue(inputId, value) {
  const input = document.getElementById(inputId);
  const nextValue = String(value);
  const previousAutoValue = input.dataset.autoValue ?? "";
  const manual = input.dataset.manual === "true";

  if (!manual || input.value === "" || input.value === previousAutoValue) {
    input.value = nextValue;
    input.dataset.manual = "false";
  }

  input.dataset.autoValue = nextValue;
}

function splitLines(value) {
  return value
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}

function getChecked(name) {
  return Array.from(document.querySelectorAll(`input[name="${name}"]:checked`)).map(
    (input) => input.value,
  );
}

function setChecked(name, values) {
  document.querySelectorAll(`input[name="${name}"]`).forEach((input) => {
    input.checked = values.includes(input.value);
  });
}

function fillSelect(select, values, includeEmpty = false, emptyLabel = "Не выбрано") {
  select.innerHTML = "";
  if (includeEmpty) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = emptyLabel;
    select.append(option);
  }
  values.forEach((value) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    select.append(option);
  });
}

async function loadMeta() {
  state.meta = await api("/api/meta");
  fillSelect(document.getElementById("product-category"), state.meta.product_categories);
  fillSelect(document.getElementById("product-cooking-state"), state.meta.cooking_states);
  fillSelect(
    document.getElementById("dish-category"),
    state.meta.dish_categories,
    true,
    "Выберите категорию или используйте макрос",
  );

  fillSelect(
    document.getElementById("product-filter-category"),
    state.meta.product_categories,
    true,
    "Все категории",
  );
  fillSelect(
    document.getElementById("product-filter-cooking"),
    state.meta.cooking_states,
    true,
    "Любая готовность",
  );
  fillSelect(
    document.getElementById("dish-filter-category"),
    state.meta.dish_categories,
    true,
    "Все категории",
  );
}

function productFilters() {
  const params = new URLSearchParams();
  const search = document.getElementById("product-search").value.trim();
  const category = document.getElementById("product-filter-category").value;
  const cooking = document.getElementById("product-filter-cooking").value;
  const sortBy = document.getElementById("product-sort").value;
  const flags = getChecked("product-filter-flag");

  if (search) params.set("query", search);
  if (category) params.set("category", category);
  if (cooking) params.set("cooking_state", cooking);
  flags.forEach((flag) => params.append("flag", flag));
  params.set("sort_by", sortBy);
  return params.toString();
}

function dishFilters() {
  const params = new URLSearchParams();
  const search = document.getElementById("dish-search").value.trim();
  const category = document.getElementById("dish-filter-category").value;
  const flags = getChecked("dish-filter-flag");
  if (search) params.set("query", search);
  if (category) params.set("category", category);
  flags.forEach((flag) => params.append("flag", flag));
  return params.toString();
}

async function loadProducts() {
  state.products = await api(`/api/products?${productFilters()}`);
  renderProducts();
  renderIngredientOptions();
}

async function loadDishes() {
  state.dishes = await api(`/api/dishes?${dishFilters()}`);
  renderDishes();
}

function renderProducts() {
  const container = document.getElementById("product-list");
  container.innerHTML = "";
  if (!state.products.length) {
    container.innerHTML = '<div class="hint-card">Пока нет продуктов.</div>';
    return;
  }

  state.products.forEach((product) => {
    const photo = renderGallery(product.photos, product.name);
    const card = document.createElement("article");
    card.className = "card";
    card.innerHTML = `
      ${photo}
      <h3>${product.name}</h3>
      <div class="meta">
        <span class="chip">${product.category}</span>
        <span class="chip">${product.cooking_state}</span>
      </div>
      <p class="small">КБЖУ: ${product.calories} / ${product.protein} / ${product.fat} / ${product.carbs}</p>
      <p class="small">${product.composition || "Состав не указан"}</p>
      <div class="flags-row">${product.flags.map((flag) => `<span class="chip">${flag}</span>`).join("")}</div>
      <div class="inline-actions">
        <button type="button" class="ghost-button" data-action="view-product" data-id="${product.id}">Открыть</button>
        <button type="button" data-action="edit-product" data-id="${product.id}">Редактировать</button>
        <button type="button" class="ghost-button" data-action="delete-product" data-id="${product.id}">Удалить</button>
      </div>
    `;
    container.append(card);
  });
}

function renderDishes() {
  const container = document.getElementById("dish-list");
  container.innerHTML = "";
  if (!state.dishes.length) {
    container.innerHTML = '<div class="hint-card">Пока нет блюд.</div>';
    return;
  }

  state.dishes.forEach((dish) => {
    const photo = renderGallery(dish.photos, dish.name);
    const ingredients = dish.ingredients
      .map((ingredient) => `<li><strong>${ingredient.product_name}</strong>: ${ingredient.quantity} г</li>`)
      .join("");
    const card = document.createElement("article");
    card.className = "card";
    card.innerHTML = `
      ${photo}
      <h3>${dish.name}</h3>
      <div class="meta">
        <span class="chip">${dish.category}</span>
        <span class="chip">${dish.portion_size} г</span>
      </div>
      <p class="small">КБЖУ: ${dish.calories} / ${dish.protein} / ${dish.fat} / ${dish.carbs}</p>
      <p class="small">Авторасчёт: ${dish.suggested_nutrition.calories} / ${dish.suggested_nutrition.protein} / ${dish.suggested_nutrition.fat} / ${dish.suggested_nutrition.carbs}</p>
      <div class="ingredient-block">
        <p class="small"><strong>Ингредиенты:</strong></p>
        <ul class="ingredient-view">${ingredients}</ul>
      </div>
      <div class="flags-row">${dish.flags.map((flag) => `<span class="chip">${flag}</span>`).join("")}</div>
      <div class="inline-actions">
        <button type="button" class="ghost-button" data-action="view-dish" data-id="${dish.id}">Открыть</button>
        <button type="button" data-action="edit-dish" data-id="${dish.id}">Редактировать</button>
        <button type="button" class="ghost-button" data-action="delete-dish" data-id="${dish.id}">Удалить</button>
      </div>
    `;
    container.append(card);
  });
}

function resetProductForm() {
  document.getElementById("product-form").reset();
  document.getElementById("product-id").value = "";
  setChecked("product-flag", []);
}

function resetDishForm() {
  document.getElementById("dish-form").reset();
  document.getElementById("dish-id").value = "";
  document.getElementById("dish-ingredients").innerHTML = "";
  addIngredientRow();
  setChecked("dish-flag", []);
  markDishNutritionAsAuto();
  updateDishPreview();
}

function addIngredientRow(ingredient = null) {
  const row = document.createElement("div");
  row.className = "ingredient-entry";
  row.innerHTML = `
    <select class="ingredient-product"></select>
    <input class="ingredient-quantity" type="number" min="0.01" step="0.01" placeholder="Количество, г" />
    <button type="button" class="ghost-button ingredient-remove">Удалить</button>
  `;
  document.getElementById("dish-ingredients").append(row);

  const select = row.querySelector(".ingredient-product");
  renderIngredientOptions(select);
  if (ingredient) {
    select.value = ingredient.product_id;
    row.querySelector(".ingredient-quantity").value = ingredient.quantity;
  }

  row.querySelector(".ingredient-remove").addEventListener("click", () => {
    row.remove();
    if (!document.querySelector(".ingredient-entry")) addIngredientRow();
    updateDishPreview();
  });
  row.querySelector(".ingredient-product").addEventListener("change", updateDishPreview);
  row.querySelector(".ingredient-quantity").addEventListener("input", updateDishPreview);
}

function renderIngredientOptions(targetSelect = null) {
  const selects = targetSelect
    ? [targetSelect]
    : Array.from(document.querySelectorAll(".ingredient-product"));
  selects.forEach((select) => {
    const currentValue = select.value;
    select.innerHTML = '<option value="">Выберите продукт</option>';
    state.products.forEach((product) => {
      const option = document.createElement("option");
      option.value = product.id;
      option.textContent = product.name;
      select.append(option);
    });
    select.value = currentValue;
  });
}

function collectIngredients() {
  return Array.from(document.querySelectorAll(".ingredient-entry"))
    .map((row) => ({
      product_id: row.querySelector(".ingredient-product").value,
      quantity: row.querySelector(".ingredient-quantity").value,
    }))
    .filter((item) => item.product_id && item.quantity);
}

async function updateDishPreview() {
  const params = new URLSearchParams();
  const name = document.getElementById("dish-name").value.trim();
  const category = document.getElementById("dish-category").value;
  if (name) params.set("query", name);
  if (category) params.set("category", category);
  collectIngredients().forEach((ingredient) => {
    params.append("ingredient", `${ingredient.product_id}:${ingredient.quantity}`);
  });

  const previewBox = document.getElementById("dish-preview");
  if (!collectIngredients().length || !name) {
    previewBox.textContent =
      "Введите название и состав блюда, чтобы увидеть авторасчёт КБЖУ и доступные флаги.";
    document.querySelectorAll('input[name="dish-flag"]').forEach((input) => {
      input.disabled = false;
    });
    return;
  }

  try {
    const preview = await api(`/api/dishes/preview?${params.toString()}`);
    applySuggestedValue("dish-calories", preview.suggested_nutrition.calories);
    applySuggestedValue("dish-protein", preview.suggested_nutrition.protein);
    applySuggestedValue("dish-fat", preview.suggested_nutrition.fat);
    applySuggestedValue("dish-carbs", preview.suggested_nutrition.carbs);
    if (!category && preview.effective_category) {
      document.getElementById("dish-category").value = preview.effective_category;
    }
    previewBox.innerHTML = `
      <strong>Авторасчёт:</strong> ${preview.suggested_nutrition.calories} / ${preview.suggested_nutrition.protein} / ${preview.suggested_nutrition.fat} / ${preview.suggested_nutrition.carbs}
      <br />
      <strong>Имя после макроса:</strong> ${preview.normalized_name}
      <br />
      <strong>Категория:</strong> ${preview.effective_category || "не выбрана"}
      <br />
      <strong>Доступные флаги:</strong> ${preview.available_flags.join(", ") || "нет"}
    `;
    document.querySelectorAll('input[name="dish-flag"]').forEach((input) => {
      input.disabled = !preview.available_flags.includes(input.value);
      if (input.disabled) input.checked = false;
    });
  } catch (error) {
    previewBox.textContent = error.message;
  }
}

function productPayload() {
  return {
    name: document.getElementById("product-name").value.trim(),
    category: document.getElementById("product-category").value,
    cooking_state: document.getElementById("product-cooking-state").value,
    calories: document.getElementById("product-calories").value,
    protein: document.getElementById("product-protein").value,
    fat: document.getElementById("product-fat").value,
    carbs: document.getElementById("product-carbs").value,
    composition: document.getElementById("product-composition").value.trim(),
    photos: splitLines(document.getElementById("product-photos").value),
    flags: getChecked("product-flag"),
  };
}

function dishPayload() {
  const valueOrNull = (id) => {
    const value = document.getElementById(id).value.trim();
    return value ? value : null;
  };

  return {
    name: document.getElementById("dish-name").value.trim(),
    category: document.getElementById("dish-category").value,
    portion_size: document.getElementById("dish-portion-size").value,
    photos: splitLines(document.getElementById("dish-photos").value),
    ingredients: collectIngredients(),
    calories: valueOrNull("dish-calories"),
    protein: valueOrNull("dish-protein"),
    fat: valueOrNull("dish-fat"),
    carbs: valueOrNull("dish-carbs"),
    flags: getChecked("dish-flag"),
  };
}

async function submitProduct(event) {
  event.preventDefault();
  const id = document.getElementById("product-id").value;
  try {
    await api(id ? `/api/products/${id}` : "/api/products", {
      method: id ? "PUT" : "POST",
      body: JSON.stringify(productPayload()),
    });
    showToast(id ? "Продукт обновлён." : "Продукт создан.");
    resetProductForm();
    await loadProducts();
    await loadDishes();
  } catch (error) {
    showToast(error.message);
  }
}

async function submitDish(event) {
  event.preventDefault();
  const id = document.getElementById("dish-id").value;
  try {
    await api(id ? `/api/dishes/${id}` : "/api/dishes", {
      method: id ? "PUT" : "POST",
      body: JSON.stringify(dishPayload()),
    });
    showToast(id ? "Блюдо обновлено." : "Блюдо создано.");
    resetDishForm();
    await loadDishes();
  } catch (error) {
    showToast(error.message);
  }
}

function fillProductForm(product) {
  document.getElementById("product-id").value = product.id;
  document.getElementById("product-name").value = product.name;
  document.getElementById("product-category").value = product.category;
  document.getElementById("product-cooking-state").value = product.cooking_state;
  document.getElementById("product-calories").value = product.calories;
  document.getElementById("product-protein").value = product.protein;
  document.getElementById("product-fat").value = product.fat;
  document.getElementById("product-carbs").value = product.carbs;
  document.getElementById("product-composition").value = product.composition || "";
  document.getElementById("product-photos").value = (product.photos || []).join("\n");
  setChecked("product-flag", product.flags || []);
}

function fillDishForm(dish) {
  document.getElementById("dish-id").value = dish.id;
  document.getElementById("dish-name").value = dish.name;
  document.getElementById("dish-category").value = dish.category;
  document.getElementById("dish-portion-size").value = dish.portion_size;
  document.getElementById("dish-photos").value = (dish.photos || []).join("\n");
  document.getElementById("dish-calories").value = dish.calories;
  document.getElementById("dish-protein").value = dish.protein;
  document.getElementById("dish-fat").value = dish.fat;
  document.getElementById("dish-carbs").value = dish.carbs;
  dishNutritionFields.forEach((id) => {
    const input = document.getElementById(id);
    input.dataset.autoValue = String(input.value);
    input.dataset.manual = "false";
  });
  document.getElementById("dish-ingredients").innerHTML = "";
  dish.ingredients.forEach(addIngredientRow);
  setChecked("dish-flag", dish.flags || []);
  updateDishPreview();
}

function renderProductDetails(product) {
  return `
    ${renderGallery(product.photos, product.name)}
    <div class="detail-grid">
      <div class="detail-item"><strong>Название:</strong> ${product.name}</div>
      <div class="detail-item"><strong>Категория:</strong> ${product.category}</div>
      <div class="detail-item"><strong>Готовность:</strong> ${product.cooking_state}</div>
      <div class="detail-item"><strong>Калории:</strong> ${product.calories} ккал / 100 г</div>
      <div class="detail-item"><strong>Белки:</strong> ${product.protein} г / 100 г</div>
      <div class="detail-item"><strong>Жиры:</strong> ${product.fat} г / 100 г</div>
      <div class="detail-item"><strong>Углеводы:</strong> ${product.carbs} г / 100 г</div>
      <div class="detail-item"><strong>Состав:</strong> ${product.composition || "Не указан"}</div>
      <div class="detail-item"><strong>Флаги:</strong> ${product.flags.join(", ") || "Нет"}</div>
      <div class="detail-item"><strong>Создан:</strong> ${product.created_at}</div>
      <div class="detail-item"><strong>Изменён:</strong> ${product.updated_at || "Ещё не редактировался"}</div>
    </div>
  `;
}

function renderDishDetails(dish) {
  const ingredients = dish.ingredients
    .map((ingredient) => `<li><strong>${ingredient.product_name}</strong>: ${ingredient.quantity} г</li>`)
    .join("");
  return `
    ${renderGallery(dish.photos, dish.name)}
    <div class="detail-grid">
      <div class="detail-item"><strong>Название:</strong> ${dish.name}</div>
      <div class="detail-item"><strong>Категория:</strong> ${dish.category}</div>
      <div class="detail-item"><strong>Размер порции:</strong> ${dish.portion_size} г</div>
      <div class="detail-item"><strong>Калории:</strong> ${dish.calories} ккал / порция</div>
      <div class="detail-item"><strong>Белки:</strong> ${dish.protein} г / порция</div>
      <div class="detail-item"><strong>Жиры:</strong> ${dish.fat} г / порция</div>
      <div class="detail-item"><strong>Углеводы:</strong> ${dish.carbs} г / порция</div>
      <div class="detail-item"><strong>Авторасчёт:</strong> ${dish.suggested_nutrition.calories} / ${dish.suggested_nutrition.protein} / ${dish.suggested_nutrition.fat} / ${dish.suggested_nutrition.carbs}</div>
      <div class="detail-item"><strong>Флаги:</strong> ${dish.flags.join(", ") || "Нет"}</div>
      <div class="detail-item"><strong>Доступные флаги:</strong> ${(dish.available_flags || []).join(", ") || "Нет"}</div>
      <div class="detail-item detail-item-full">
        <strong>Ингредиенты:</strong>
        <ul class="ingredient-view">${ingredients}</ul>
      </div>
      <div class="detail-item"><strong>Создан:</strong> ${dish.created_at}</div>
      <div class="detail-item"><strong>Изменён:</strong> ${dish.updated_at || "Ещё не редактировался"}</div>
    </div>
  `;
}

async function onCardAction(event) {
  const button = event.target.closest("button[data-action]");
  if (!button) return;

  const { action, id } = button.dataset;
  try {
    if (action === "view-product") {
      const product = await api(`/api/products/${id}`);
      openModal("Карточка продукта", renderProductDetails(product));
    }
    if (action === "edit-product") {
      fillProductForm(await api(`/api/products/${id}`));
    }
    if (action === "delete-product") {
      await api(`/api/products/${id}`, { method: "DELETE" });
      showToast("Продукт удалён.");
      await loadProducts();
      await loadDishes();
    }
    if (action === "view-dish") {
      const dish = await api(`/api/dishes/${id}`);
      openModal("Карточка блюда", renderDishDetails(dish));
    }
    if (action === "edit-dish") {
      fillDishForm(await api(`/api/dishes/${id}`));
    }
    if (action === "delete-dish") {
      await api(`/api/dishes/${id}`, { method: "DELETE" });
      showToast("Блюдо удалено.");
      await loadDishes();
    }
  } catch (error) {
    if (action === "delete-product" && error.payload?.used_by?.length) {
      const dishNames = error.payload.used_by.map((dish) => dish.name).join(", ");
      showToast(`${error.message} Используется в блюдах: ${dishNames}.`);
      return;
    }
    showToast(error.message);
  }
}

async function init() {
  await loadMeta();
  document.getElementById("product-form").addEventListener("submit", submitProduct);
  document.getElementById("dish-form").addEventListener("submit", submitDish);
  document.getElementById("reset-product").addEventListener("click", resetProductForm);
  document.getElementById("reset-dish").addEventListener("click", resetDishForm);
  document.getElementById("reload-products").addEventListener("click", loadProducts);
  document.getElementById("reload-dishes").addEventListener("click", loadDishes);
  document.getElementById("add-ingredient").addEventListener("click", () => addIngredientRow());
  document.getElementById("product-list").addEventListener("click", onCardAction);
  document.getElementById("dish-list").addEventListener("click", onCardAction);
  document.getElementById("close-modal").addEventListener("click", closeModal);
  document.querySelector('[data-close-modal="true"]').addEventListener("click", closeModal);
  dishNutritionFields.forEach((id) => {
    document.getElementById(id).addEventListener("input", () => {
      document.getElementById(id).dataset.manual = "true";
    });
  });

  ["product-search", "product-filter-category", "product-filter-cooking", "product-sort"].forEach((id) =>
    document.getElementById(id).addEventListener("input", loadProducts),
  );
  document.querySelectorAll('input[name="product-filter-flag"]').forEach((input) =>
    input.addEventListener("change", loadProducts),
  );
  ["dish-search", "dish-filter-category"].forEach((id) =>
    document.getElementById(id).addEventListener("input", loadDishes),
  );
  document.querySelectorAll('input[name="dish-filter-flag"]').forEach((input) =>
    input.addEventListener("change", loadDishes),
  );
  ["dish-name", "dish-category", "dish-portion-size"].forEach((id) =>
    document.getElementById(id).addEventListener("input", updateDishPreview),
  );

  await loadProducts();
  await loadDishes();
  resetDishForm();
  resetProductForm();
}

init().catch((error) => showToast(error.message));
