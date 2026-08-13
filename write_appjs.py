code = open("frontend/app.js", "w", encoding="utf-8")
code.write("""/* TRAFFIC DASHBOARD */
let charts = {};
let signalTimer = null;

document.addEventListener("DOMContentLoaded", function() {
  initTabs();
  startClock();
  loadAll();
});

async function loadAll() {
  await checkStatus();
  await loadStats();
  await loadPrediction();
  await loadForecast();
  await loadHistory();
}

function startClock() {
  function tick() {
    var el = document.getElementById("clock");
    if (el) el.textContent = new Date().toLocaleString();
  }
  tick();
  setInterval(tick, 1000);
}

function initTabs() {
  var tabs = document.querySelectorAll(".tab");
  tabs.forEach(function(btn) {
    btn.addEventListener("click", function() {
      tabs.forEach(function(b) { b.classList.remove("active"); });
      document.querySelectorAll(".tab-content").forEach(function(p) {
        p.classList.remove("active");
      });
      btn.classList.add("active");
      var page = document.getElementById("tab-" + btn.dataset.tab);
      if (page) page.classList.add("active");
    });
  });
}

function setCard(id, value) {
  var el = document.getElementById(id);
  if (el) {
    el.textContent = value;
  } else {
    console.error("Not found: " + id);
  }
}

async function checkStatus() {
  try {
    var res  = await fetch("/api/status");
    var data = await res.json();
    var badge = document.getElementById("statusBadge");
    if (badge) {
      badge.textContent = data.model_ready ? "Model Ready" : "Mock Mode";
      badge.className   = "badge ok";
    }
  } catch(e) { console.error("Status failed:", e); }
}

async function loadStats() {
  try {
    var res  = await fetch("/api/stats");
    var data = await res.json();
    console.log("Stats:", data);
    if (!data.success) return;
    var s = data.stats;
    setCard("avgDaily",  Math.round(s.avg_daily_volume));
    setCard("peakHour",  s.peak_hour);
    setCard("incidents", s.incident_count);
    if (s.hourly_pattern) renderPatternChart(s.hourly_pattern);
    renderIntersectionGrid(s);
  } catch(e) { console.error("Stats error:", e); }
}

async function loadPrediction() {
  try {
    var res  = await fetch("/api/predict");
    var data = await res.json();
    console.log("Predict:", data);
    if (!data.success) return;
    var p = data.prediction;
    setCard("totalVolume",     p.total_volume);
    setCard("congestionLevel", p.congestion_level);
    setCard("avgSpeed",        p.avg_speed_kmh);
    if (p.signal_timing) {
      updateSignals(p.signal_timing, p.total_volume);
      renderSignalChart(p.signal_timing);
    }
  } catch(e) { console.error("Predict error:", e); }
}

async function trainModel() {
  var btn    = document.getElementById("trainBtn");
  var status = document.getElementById("trainStatus");
  btn.disabled    = true;
  btn.textContent = "Training...";
  if (status) {
    status.textContent = "Training (~30 sec)...";
    status.style.color = "#f59e0b";
  }
  try {
    var res  = await fetch("/api/train");
    var data = await res.json();
    if (data.success) {
      if (status) {
        status.textContent = "Done! " + data.message;
        status.style.color = "#10b981";
      }
      await checkStatus();
      await loadPrediction();
      await loadStats();
    } else {
      if (status) {
        status.textContent = "Error: " + data.error;
        status.style.color = "#ef4444";
      }
    }
  } catch(e) {
    if (status) {
      status.textContent = "Failed: " + e.message;
      status.style.color = "#ef4444";
    }
  }
  btn.disabled    = false;
  btn.textContent = "Train Model";
}

async function loadForecast() {
  try {
    var res  = await fetch("/api/forecast");
    var data = await res.json();
    if (!data.success) return;
    renderForecastChart(data.forecast);
    renderForecastTable(data.forecast);
  } catch(e) { console.error("Forecast error:", e); }
}

async function loadHistory() {
  try {
    var sel   = document.getElementById("hoursSelect");
    var hours = sel ? sel.value : 48;
    var res   = await fetch("/api/history?hours=" + hours);
    var data  = await res.json();
    if (!data.success) return;
    renderHistoryChart(data.data);
    renderHistoryTable(data.data);
  } catch(e) { console.error("History error:", e); }
}

async function runOptimize() {
  try {
    var body = {
      north  : parseInt(document.getElementById("inp-north").value)   || 400,
      south  : parseInt(document.getElementById("inp-south").value)   || 400,
      east   : parseInt(document.getElementById("inp-east").value)    || 400,
      west   : parseInt(document.getElementById("inp-west").value)    || 400,
      weather: parseInt(document.getElementById("inp-weather").value) || 0,
    };
    var res  = await fetch("/api/optimize", {
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body: JSON.stringify(body)
    });
    var data = await res.json();
    if (!data.success) { alert("Error: " + data.error); return; }
    var opt     = data.optimized;
    var results = document.getElementById("optimizeResults");
    if (results) results.style.display = "block";
    renderOptimizeChart(opt.signal_timing);
    renderResultCards(opt);
    renderRecommendations(opt.recommendations);
  } catch(e) { console.error("Optimize error:", e); }
}

function updateSignals(timing, totalVolume) {
  var vol   = Math.round((totalVolume || 0) / 4);
  var pairs = [["n","north"],["s","south"],["e","east"],["w","west"]];
  pairs.forEach(function(pair) {
    var t = document.getElementById(pair[0]+"-time");
    var v = document.getElementById(pair[0]+"-vol");
    if (t) t.textContent = (timing[pair[1]]||30) + " sec";
    if (v) v.textContent = vol + " vehicles";
  });
  animateSignals(timing);
}

function animateSignals(timing) {
  if (signalTimer) clearTimeout(signalTimer);
  function setLight(p, color) {
    ["red","yellow","green"].forEach(function(c) {
      var el = document.getElementById(p+"-"+c);
      if (el) el.classList.remove("active");
    });
    var el = document.getElementById(p+"-"+color);
    if (el) el.classList.add("active");
  }
  var phase = 0;
  function run() {
    if (phase===0) {
      setLight("n","green"); setLight("s","green");
      setLight("e","red");   setLight("w","red");
      signalTimer = setTimeout(function(){phase=1;run();},(timing.north||30)*200);
    } else if (phase===1) {
      ["n","s","e","w"].forEach(function(p){setLight(p,"yellow");});
      signalTimer = setTimeout(function(){phase=2;run();},2000);
    } else if (phase===2) {
      setLight("n","red");   setLight("s","red");
      setLight("e","green"); setLight("w","green");
      signalTimer = setTimeout(function(){phase=3;run();},(timing.east||30)*200);
    } else {
      ["n","s","e","w"].forEach(function(p){setLight(p,"yellow");});
      signalTimer = setTimeout(function(){phase=0;run();},2000);
    }
  }
  run();
}

function renderIntersectionGrid(stats) {
  var grid = document.getElementById("intersectionGrid");
  if (!grid) return;
  var avg   = stats.avg_hourly_volume || 400;
  var items = [
    {name:"North",icon:"N",vol:Math.round(avg*1.0)},
    {name:"South",icon:"S",vol:Math.round(avg*0.9)},
    {name:"East", icon:"E",vol:Math.round(avg*1.1)},
    {name:"West", icon:"W",vol:Math.round(avg*0.85)},
  ];
  grid.innerHTML = items.map(function(item) {
    var level = item.vol>800?"high":item.vol>400?"medium":"low";
    var green = Math.round(Math.min(90,20+item.vol/15));
    return "<div class='intersection-item "+level+"'>"+
      "<div class='inter-name'>"+item.icon+" "+item.name+"</div>"+
      "<div class='inter-detail'>Volume: <strong>"+item.vol+"</strong> vehicles/hr</div>"+
      "<div class='inter-detail'>Green: <strong>"+green+"s</strong></div>"+
      "<div class='inter-detail'>Status: <strong>"+level.toUpperCase()+"</strong></div>"+
      "</div>";
  }).join("");
}

function renderResultCards(opt) {
  var cards = document.getElementById("resultCards");
  if (!cards) return;
  var dirs = [
    {name:"North",icon:"N",key:"north"},
    {name:"South",icon:"S",key:"south"},
    {name:"East", icon:"E",key:"east"},
    {name:"West", icon:"W",key:"west"}
  ];
  var html = "<div class='result-card'>"+
    "<div class='direction-name'>Total Volume</div>"+
    "<div class='timing'>"+opt.total_volume+"</div>"+
    "<div class='timing-unit'>vehicles/hr</div></div>"+
    "<div class='result-card'>"+
    "<div class='direction-name'>Congestion</div>"+
    "<div class='timing'>"+opt.congestion_level+"</div>"+
    "<div class='timing-unit'>"+Math.round(opt.congestion*100)+"%</div></div>";
  dirs.forEach(function(d) {
    html += "<div class='result-card'>"+
      "<div class='direction-name'>"+d.name+"</div>"+
      "<div class='timing'>"+opt.signal_timing[d.key]+"</div>"+
      "<div class='timing-unit'>sec green</div></div>";
  });
  cards.innerHTML = html;
}

function renderRecommendations(recs) {
  var list = document.getElementById("recommendationsList");
  if (!list) return;
  if (!recs||recs.length===0) {
    list.innerHTML = "<p style='color:#8b949e;padding:10px'>Traffic flowing well.</p>";
    return;
  }
  list.innerHTML = recs.map(function(r){
    return "<div class='rec-item'>"+r+"</div>";
  }).join("");
}

function renderForecastTable(forecast) {
  var tbody = document.querySelector("#forecastTable tbody");
  if (!tbody) return;
  tbody.innerHTML = forecast.map(function(f) {
    return "<tr><td>"+f.label+"</td><td>"+f.volume+"</td>"+
      "<td>"+Math.round(f.congestion*100)+"%</td>"+
      "<td>"+f.avg_speed+" km/h</td><td>"+f.green_time+"s</td>"+
      "<td><span class='status-badge status-"+f.congestion_level.toLowerCase()+"'>"+
      f.congestion_level+"</span></td></tr>";
  }).join("");
}

function renderHistoryTable(data) {
  var tbody = document.querySelector("#historyTable tbody");
  if (!tbody) return;
  var slice = data.slice(-24).reverse();
  tbody.innerHTML = slice.map(function(r) {
    var d = new Date(r.timestamp);
    return "<tr><td>"+d.toLocaleString()+"</td><td>"+r.volume+"</td>"+
      "<td>"+r.avg_speed+"</td><td>"+Math.round(r.congestion*100)+"%</td>"+
      "<td>"+r.weather+"</td><td>"+(r.incident?"Yes":"No")+"</td></tr>";
  }).join("");
}

function tip() {
  return {backgroundColor:"#161b22",titleColor:"#e6edf3",
    bodyColor:"#8b949e",borderColor:"#30363d",borderWidth:1,padding:10};
}
function sc() {
  return {grid:{color:"rgba(255,255,255,.05)"},
    ticks:{color:"#6b7280",font:{size:11}}};
}

function renderPatternChart(pattern) {
  var ctx = document.getElementById("patternChart");
  if (!ctx) return;
  if (charts["pattern"]) charts["pattern"].destroy();
  var labels = Object.keys(pattern).map(function(h){return h+":00";});
  var values = Object.values(pattern);
  var colors = Object.keys(pattern).map(function(h) {
    h=parseInt(h);
    if((h>=7&&h<=9)||(h>=17&&h<=19)) return "rgba(239,68,68,.8)";
    if(h>=0&&h<=5) return "rgba(16,185,129,.8)";
    return "rgba(59,130,246,.8)";
  });
  charts["pattern"] = new Chart(ctx,{
    type:"bar",
    data:{labels:labels,datasets:[{
      data:values,backgroundColor:colors,
      borderRadius:5,borderSkipped:false}]},
    options:{responsive:true,maintainAspectRatio:false,
      plugins:{legend:{display:false},tooltip:tip()},
      scales:{x:sc(),y:Object.assign({},sc(),{
        title:{display:true,text:"Vehicles/hr",color:"#6b7280"}})}}
  });
}

function renderSignalChart(timing) {
  var ctx = document.getElementById("signalChart");
  if (!ctx) return;
  if (charts["signal"]) charts["signal"].destroy();
  charts["signal"] = new Chart(ctx,{
    type:"bar",
    data:{labels:["North","South","East","West"],datasets:[{
      label:"Green Time (s)",
      data:[timing.north||30,timing.south||30,timing.east||30,timing.west||30],
      backgroundColor:["rgba(16,185,129,.8)","rgba(59,130,246,.8)",
        "rgba(245,158,11,.8)","rgba(139,92,246,.8)"],
      borderRadius:8,borderSkipped:false}]},
    options:{responsive:true,maintainAspectRatio:false,
      plugins:{legend:{display:false},tooltip:tip()},
      scales:{x:sc(),y:Object.assign({},sc(),{
        min:0,max:100,title:{display:true,text:"Seconds",color:"#6b7280"}})}}
  });
}

function renderForecastChart(forecast) {
  var ctx = document.getElementById("forecastChart");
  if (!ctx) return;
  if (charts["forecast"]) charts["forecast"].destroy();
  charts["forecast"] = new Chart(ctx,{
    type:"line",
    data:{
      labels:forecast.map(function(f){return f.label;}),
      datasets:[
        {label:"Traffic Volume",
         data:forecast.map(function(f){return f.volume;}),
         borderColor:"#3b82f6",backgroundColor:"rgba(59,130,246,.1)",
         fill:true,tension:0.4,borderWidth:2,pointRadius:3,yAxisID:"y"},
        {label:"Avg Speed",
         data:forecast.map(function(f){return f.avg_speed;}),
         borderColor:"#10b981",backgroundColor:"transparent",
         borderDash:[5,4],tension:0.4,borderWidth:2,pointRadius:2,yAxisID:"y2"}
      ]},
    options:{responsive:true,maintainAspectRatio:false,
      interaction:{mode:"index",intersect:false},
      plugins:{legend:{display:true,
        labels:{color:"#8b949e",font:{size:12},usePointStyle:true}},
        tooltip:tip()},
      scales:{x:sc(),
        y:Object.assign({},sc(),{title:{display:true,text:"Vehicles/hr",
          color:"#6b7280"},position:"left"}),
        y2:Object.assign({},sc(),{title:{display:true,text:"km/h",
          color:"#6b7280"},position:"right",grid:{drawOnChartArea:false}})}}
  });
}

function renderHistoryChart(data) {
  var ctx = document.getElementById("historyChart");
  if (!ctx) return;
  if (charts["history"]) charts["history"].destroy();
  var step   = data.length>100?2:1;
  var points = data.filter(function(_,i){return i%step===0;});
  charts["history"] = new Chart(ctx,{
    type:"line",
    data:{
      labels:points.map(function(r){
        var d=new Date(r.timestamp);
        return d.toLocaleString("en-US",{month:"short",day:"numeric",hour:"2-digit"});
      }),
      datasets:[
        {label:"Traffic Volume",
         data:points.map(function(r){return r.volume;}),
         borderColor:"#3b82f6",backgroundColor:"rgba(59,130,246,.08)",
         fill:true,tension:0.3,borderWidth:1.5,pointRadius:0,yAxisID:"y"},
        {label:"Avg Speed",
         data:points.map(function(r){return r.avg_speed;}),
         borderColor:"#10b981",backgroundColor:"transparent",
         borderDash:[4,3],tension:0.3,borderWidth:1.5,pointRadius:0,yAxisID:"y2"}
      ]},
    options:{responsive:true,maintainAspectRatio:false,
      interaction:{mode:"index",intersect:false},
      plugins:{legend:{display:true,
        labels:{color:"#8b949e",font:{size:12},usePointStyle:true}},
        tooltip:tip()},
      scales:{
        x:Object.assign({},sc(),{ticks:Object.assign({},sc().ticks,
          {maxTicksLimit:10,maxRotation:45})}),
        y:Object.assign({},sc(),{title:{display:true,text:"Vehicles/hr",
          color:"#6b7280"},position:"left"}),
        y2:Object.assign({},sc(),{title:{display:true,text:"km/h",
          color:"#6b7280"},position:"right",grid:{drawOnChartArea:false}})}}
  });
}

function renderOptimizeChart(timing) {
  var ctx = document.getElementById("optimizeChart");
  if (!ctx) return;
  if (charts["optimize"]) charts["optimize"].destroy();
  charts["optimize"] = new Chart(ctx,{
    type:"bar",
    data:{labels:["North","South","East","West"],datasets:[{
      label:"Green Time (s)",
      data:[timing.north||30,timing.south||30,timing.east||30,timing.west||30],
      backgroundColor:["rgba(16,185,129,.8)","rgba(59,130,246,.8)",
        "rgba(245,158,11,.8)","rgba(139,92,246,.8)"],
      borderRadius:8,borderSkipped:false}]},
    options:{responsive:true,maintainAspectRatio:false,
      plugins:{legend:{display:false},tooltip:tip()},
      scales:{x:sc(),y:Object.assign({},sc(),{min:0,max:100,
        title:{display:true,text:"Green Time (s)",color:"#6b7280"}})}}
  });
}
""")
code.close()
print("Done! app.js written successfully.")