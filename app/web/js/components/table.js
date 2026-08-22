/* The one reusable paginated-table component every list page uses (dashboard trend tables,
domains, records, scan queue, cleanup, audit, ingest history). Matches the server-side
pagination contract in app/api/pagination.py: {rows, total, limit, offset, sort_by, sort_dir}.
Supports quiet refresh (no loading veil, page/sort/filters preserved) for live-polling pages,
a page-size selector, sortable headers, and CSS drag-resizable columns via a <colgroup>. */

export class PaginatedTable {
  constructor(container, { columns, fetchPage, defaultSort, pageSize = 50, onRowClick } = {}) {
    this.container = container;
    this.columns = columns;
    this.fetchPage = fetchPage;
    this.onRowClick = onRowClick;
    this.state = {
      limit: pageSize,
      offset: 0,
      sort_by: defaultSort?.by ?? columns.find((c) => c.sortable)?.key ?? columns[0].key,
      sort_dir: defaultSort?.dir ?? "asc",
    };
    this._buildShell();
  }

  _buildShell() {
    this.container.innerHTML = `
      <div class="table-wrap">
        <table class="data-table">
          <colgroup></colgroup>
          <thead></thead>
          <tbody></tbody>
        </table>
        <div class="table-toolbar">
          <div class="result-count"></div>
          <div class="pager">
            <label>Rows
              <select class="page-size">
                <option value="20">20</option>
                <option value="50">50</option>
                <option value="100">100</option>
                <option value="200">200</option>
              </select>
            </label>
            <button type="button" class="prev">&larr; Prev</button>
            <span class="page-label"></span>
            <button type="button" class="next">Next &rarr;</button>
          </div>
        </div>
      </div>`;
    this.colgroupEl = this.container.querySelector("colgroup");
    this.theadEl = this.container.querySelector("thead");
    this.tbodyEl = this.container.querySelector("tbody");
    this.tableEl = this.container.querySelector("table");
    this.countEl = this.container.querySelector(".result-count");
    this.pageLabelEl = this.container.querySelector(".page-label");
    this.prevBtn = this.container.querySelector(".prev");
    this.nextBtn = this.container.querySelector(".next");
    this.pageSizeSel = this.container.querySelector(".page-size");
    this.pageSizeSel.value = String(this.state.limit);

    for (const _ of this.columns) {
      this.colgroupEl.appendChild(document.createElement("col"));
    }

    this._renderHead();
    this.prevBtn.onclick = () => {
      this.state.offset = Math.max(0, this.state.offset - this.state.limit);
      this.refresh();
    };
    this.nextBtn.onclick = () => {
      this.state.offset += this.state.limit;
      this.refresh();
    };
    this.pageSizeSel.onchange = () => {
      this.state.limit = Number(this.pageSizeSel.value);
      this.state.offset = 0;
      this.refresh();
    };
  }

  _renderHead() {
    const tr = document.createElement("tr");
    this.columns.forEach((col, idx) => {
      const th = document.createElement("th");
      th.textContent = col.label;
      if (col.sortable) {
        th.classList.add("sortable");
        if (this.state.sort_by === col.key) {
          const arrow = document.createElement("span");
          arrow.className = "sort-arrow";
          arrow.textContent = this.state.sort_dir === "asc" ? "▲" : "▼";
          th.appendChild(arrow);
        }
        th.addEventListener("click", (e) => {
          if (e.target.classList.contains("col-resizer")) return;
          if (this.state.sort_by === col.key) {
            this.state.sort_dir = this.state.sort_dir === "asc" ? "desc" : "asc";
          } else {
            this.state.sort_by = col.key;
            this.state.sort_dir = "asc";
          }
          this.state.offset = 0;
          this.refresh();
        });
      }
      const resizer = document.createElement("span");
      resizer.className = "col-resizer";
      resizer.style.cssText =
        "display:inline-block;width:6px;cursor:col-resize;float:right;height:100%;margin-right:-8px;";
      resizer.addEventListener("pointerdown", (e) => this._startResize(e, idx));
      th.style.position = "relative";
      th.appendChild(resizer);
      tr.appendChild(th);
    });
    this.theadEl.innerHTML = "";
    this.theadEl.appendChild(tr);
  }

  _startResize(e, colIdx) {
    e.preventDefault();
    e.stopPropagation();
    const col = this.colgroupEl.children[colIdx];
    const th = this.theadEl.querySelectorAll("th")[colIdx];
    const startWidth = th.offsetWidth;
    const startX = e.clientX;
    this.tableEl.style.tableLayout = "fixed";
    const onMove = (ev) => {
      const newWidth = Math.max(50, startWidth + (ev.clientX - startX));
      col.style.width = `${newWidth}px`;
    };
    const onUp = () => {
      document.removeEventListener("pointermove", onMove);
      document.removeEventListener("pointerup", onUp);
    };
    document.addEventListener("pointermove", onMove);
    document.addEventListener("pointerup", onUp);
  }

  async refresh({ quiet = false, preservePage = true } = {}) {
    if (!preservePage) this.state.offset = 0;
    if (!quiet) this.tableEl.classList.add("table-loading-veil");
    try {
      const { rows, total } = await this.fetchPage({ ...this.state });
      this._renderRows(rows);
      this.countEl.textContent = `${total} result${total === 1 ? "" : "s"}`;
      const page = Math.floor(this.state.offset / this.state.limit) + 1;
      const pages = Math.max(1, Math.ceil(total / this.state.limit));
      this.pageLabelEl.textContent = `Page ${page} of ${pages}`;
      this.prevBtn.disabled = this.state.offset <= 0;
      this.nextBtn.disabled = this.state.offset + this.state.limit >= total;
      if (!quiet) this._renderHead();
    } finally {
      this.tableEl.classList.remove("table-loading-veil");
    }
  }

  _renderRows(rows) {
    this.tbodyEl.innerHTML = "";
    if (!rows.length) {
      const tr = document.createElement("tr");
      const td = document.createElement("td");
      td.colSpan = this.columns.length;
      td.className = "empty-state";
      td.textContent = "No results";
      tr.appendChild(td);
      this.tbodyEl.appendChild(tr);
      return;
    }
    for (const row of rows) {
      const tr = document.createElement("tr");
      if (this.onRowClick) {
        tr.style.cursor = "pointer";
        tr.addEventListener("click", () => this.onRowClick(row));
      }
      for (const col of this.columns) {
        const td = document.createElement("td");
        if (col.className) td.className = col.className;
        const content = col.render ? col.render(row) : (row[col.key] ?? "");
        if (content instanceof Node) td.appendChild(content);
        else td.textContent = content ?? "";
        tr.appendChild(td);
      }
      this.tbodyEl.appendChild(tr);
    }
  }
}
