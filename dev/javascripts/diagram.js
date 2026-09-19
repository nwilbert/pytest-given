// Home-page diagram: click opens the same artwork enlarged in a <dialog>.
// Escape closes it natively; so do the Close button and a click on the backdrop.
const open = document.querySelector('.pg-diagram-open');
const dialog = document.querySelector('.pg-diagram-dialog');
if (open && dialog) {
  open.addEventListener('click', () => dialog.showModal());
  dialog.querySelector('.pg-diagram-close').addEventListener('click', () => dialog.close());
  dialog.addEventListener('click', (event) => {
    if (event.target === dialog) dialog.close();
  });
}
