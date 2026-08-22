/* Builds a filter bar from a declarative field list and calls onChange(values) whenever any
field changes (debounced for text inputs). Shared by records/domains/cleanup/jobs/audit
pages so filter UI stays consistent. */
export function buildFilterBar(container, fields, onChange) {
  container.innerHTML = "";
  container.className = "filter-bar";
  const values = {};

  for (const field of fields) {
    const group = document.createElement("div");
    group.className = "filter-group";
    const label = document.createElement("label");
    label.textContent = field.label;
    label.htmlFor = `flt-${field.key}`;
    group.appendChild(label);

    let input;
    if (field.type === "select") {
      input = document.createElement("select");
      for (const opt of field.options) {
        const o = document.createElement("option");
        o.value = opt.value;
        o.textContent = opt.label;
        input.appendChild(o);
      }
    } else if (field.type === "checkbox") {
      input = document.createElement("input");
      input.type = "checkbox";
    } else {
      input = document.createElement("input");
      input.type = field.type || "text";
      if (field.placeholder) input.placeholder = field.placeholder;
    }
    input.id = `flt-${field.key}`;

    const isTextLike = field.type === undefined || field.type === "text" || field.type === "search";
    const handler = () => {
      values[field.key] = field.type === "checkbox" ? (input.checked ? "true" : "") : input.value;
      onChange({ ...values });
    };
    input.addEventListener(isTextLike ? "input" : "change", isTextLike ? debounce(handler, 350) : handler);

    group.appendChild(input);
    container.appendChild(group);
  }

  const clearBtn = document.createElement("button");
  clearBtn.type = "button";
  clearBtn.textContent = "Clear filters";
  clearBtn.addEventListener("click", () => {
    for (const field of fields) {
      const el = container.querySelector(`#flt-${field.key}`);
      if (!el) continue;
      if (field.type === "checkbox") el.checked = false;
      else el.value = field.type === "select" ? field.options[0].value : "";
      values[field.key] = "";
    }
    onChange({ ...values });
  });
  container.appendChild(clearBtn);

  return values;
}

function debounce(fn, ms) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
}
