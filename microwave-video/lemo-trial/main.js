const mod = await import('./film.js');
await document.fonts.load('44px SUB', '在心里估一下家务小组作业');
const F = await mod.build();
const ctx = document.getElementById('c').getContext('2d');
window.DUR = F.dur; window.EV = F.ev; window.SUBS = F.subs;
window.render = t => F.render(ctx, t);
window.READY = true;
