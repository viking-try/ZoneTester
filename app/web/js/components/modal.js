export function showModal(title, contentEl, { onClose, footerButtons = [] } = {}) {
  const backdrop = document.createElement("div");
  backdrop.className = "modal-backdrop";

  const modal = document.createElement("div");
  modal.className = "modal";

  const header = document.createElement("div");
  header.className = "modal-header";
  const h = document.createElement("h2");
  h.textContent = title;
  const closeBtn = document.createElement("button");
  closeBtn.textContent = "×";
  closeBtn.setAttribute("aria-label", "Close");
  closeBtn.onclick = () => close();
  header.append(h, closeBtn);

  modal.append(header, contentEl);

  if (footerButtons.length) {
    const footer = document.createElement("div");
    footer.className = "modal-footer";
    for (const btn of footerButtons) footer.appendChild(btn);
    modal.appendChild(footer);
  }

  backdrop.appendChild(modal);
  backdrop.addEventListener("click", (e) => {
    if (e.target === backdrop) close();
  });
  const escHandler = (e) => {
    if (e.key === "Escape") close();
  };
  document.addEventListener("keydown", escHandler);
  document.body.appendChild(backdrop);

  function close() {
    document.removeEventListener("keydown", escHandler);
    backdrop.remove();
    onClose?.();
  }

  return { close };
}
