// Small, local SVG primitives. No icon font or network dependency.
function uiIcon(name,size=20){
  const paths={
    leaf:'<path d="M20 4c-9-1-16 4-14 11 1 4 8 5 11 1 3-4 3-9 3-12Z"/><path d="m5 21 10-11"/>',
    grid:'<rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7" height="7" rx="2"/><rect x="3" y="14" width="7" height="7" rx="2"/><rect x="14" y="14" width="7" height="7" rx="2"/>',
    food:'<path d="M4 3v6a2 2 0 0 0 4 0V3M6 3v18M19 21V3c-4 2-5 8-1 9h1"/>',
    activity:'<path d="M2 12h5l3-8 4 16 3-8h5"/>',
    chart:'<path d="M4 3v17h17M8 15l4-5 4 3 5-7"/>',
    target:'<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/>',
    camera:'<path d="M8 5 10 3h4l2 2h4a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1Z"/><circle cx="12" cy="12" r="4"/>',
    backup:'<path d="M5 17a5 5 0 0 1 0-10 7 7 0 0 1 13-1 5 5 0 0 1 1 10M12 12v9m-4-4 4 4 4-4"/>',
    arrow:'<path d="M5 12h14m-5-5 5 5-5 5"/>',
    arrowUp:'<path d="M6 18 18 6M6 6h12v12"/>',
    plus:'<path d="M12 5v14M5 12h14"/>',
    fire:'<path d="M13 3c2 5-3 6-1 10 1-2 3-2 4-5 7 8 2 14-4 14-8 0-12-8-5-14-1 4 1 5 2 5-1-5 3-6 4-10Z"/>',
    water:'<path d="M12 2S5 10 5 15a7 7 0 0 0 14 0c0-5-7-13-7-13Z"/><path d="M8 15a4 4 0 0 0 4 4"/>',
    protein:'<path d="m7 3-4 4m18 10-4 4M5 5l14 14M9 2 2 9m20 6-7 7"/>',
    calendar:'<rect x="3" y="5" width="18" height="16" rx="3"/><path d="M7 3v4m10-4v4M3 11h18m-13 4h2m4 0h2"/>',
    settings:'<path d="m9 3-1 3-3 1 1 3-2 2 2 2-1 3 3 1 1 3h6l1-3 3-1-1-3 2-2-2-2 1-3-3-1-1-3Z"/><circle cx="12" cy="12" r="3"/>',
    check:'<path d="m5 12 4 4L19 6"/>',
    shield:'<path d="m12 2 8 4v6c0 5-8 10-8 10S4 17 4 12V6Z"/><path d="m8 12 3 3 5-6"/>',
    sun:'<circle cx="12" cy="12" r="4"/><path d="M12 1v2m0 18v2M1 12h2m18 0h2M4 4l2 2m12 12 2 2M4 20l2-2M18 6l2-2"/>',
    moon:'<path d="M21 13A9 9 0 0 1 11 3a9 9 0 1 0 10 10Z"/>',
    clock:'<circle cx="12" cy="12" r="9"/><path d="M12 7v6l4 2"/>',
    spark:'<path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5Z"/>',
    close:'<path d="m6 6 12 12M6 18 18 6"/>',
    lock:'<rect x="5" y="10" width="14" height="11" rx="3"/><path d="M8 10V7a4 4 0 0 1 8 0v3m-4 5v2"/>',
    upload:'<path d="M12 16V3m-4 4 4-4 4 4M4 15v5h16v-5"/>',
    bowl:'<path d="M3 11h18a9 9 0 0 1-18 0ZM8 21h8M8 7c-2-2 2-3 0-5m5 5c-2-2 2-3 0-5m5 5c-2-2 2-3 0-5"/>',
    info:'<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10v.1"/>'
  };
  return `<svg class="ui-icon" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name]||paths.leaf}</svg>`;
}
document.querySelectorAll('[data-icon]').forEach(el=>{el.innerHTML=uiIcon(el.dataset.icon);});
