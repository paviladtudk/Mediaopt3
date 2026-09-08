/* Add another blank row to a table, cloning the last one and clearing it.
   Progressive enhancement only: the server already renders two spare rows, so the form
   works with JavaScript switched off. */
document.addEventListener('click', function (e) {
  var btn = e.target.closest('.addrow');
  if (!btn) return;
  var table = document.querySelector('table[data-prefix="' + btn.dataset.prefix + '"] tbody');
  var last = table.rows[table.rows.length - 1];
  var row = last.cloneNode(true);
  var n = table.rows.length;
  row.querySelectorAll('select, input').forEach(function (el) {
    if (el.type === 'checkbox') { el.checked = false; el.value = String(n); }
    else { el.value = ''; }
  });
  table.appendChild(row);
});
