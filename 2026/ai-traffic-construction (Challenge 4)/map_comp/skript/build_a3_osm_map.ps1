<#
    build_a3_osm_map.ps1

    Option A: Echte A3-Geometrie aus OpenStreetMap (Overpass, Datei a3_osm.json),
    beide Richtungsfahrbahnen getrennt eingezeichnet (oneway-Wege).

      - Jede Richtungsfahrbahn wird in ihrer Fahrtrichtung eingefaerbt:
          Richtung Sued-Ost (Passau)      -> Blau-Toene
          Richtung Nord-West (Oberhausen) -> Rot-Toene
      - Innerhalb jeder Richtung wechseln die ABSCHNITTE die Helligkeit
        (Zuordnung ueber naechstgelegene Zaehlstelle entlang der Strecke).
      - Alle Zaehlstellen (Jawe2023, A3) als Punkt-Marker mit Popup
        (Zst, Standort, Land, Abschnitt_Ast / Spalte HW).

    Voraussetzung: a3_osm.json (Overpass-Export) liegt im Ordner.
    Aufruf: powershell -ExecutionPolicy Bypass -File .\build_a3_osm_map.ps1
#>

param(
    # Ordnerstruktur: <App>/skript (dieses Skript), <App>/rohdaten, <App>/html
    [string]$Root    = (Split-Path -Parent $PSScriptRoot),
    [string]$Jawe    = (Join-Path $Root 'rohdaten\Jawe2023.csv'),
    [string]$Osm     = (Join-Path $Root 'rohdaten\a3_osm.json'),
    [string]$OutFile = (Join-Path $Root 'html\a3_karte.html')
)

$ci = [System.Globalization.CultureInfo]::InvariantCulture

# --- 1) A3-Zaehlstellen aus Jawe2023 lesen -----------------------------------
$enc = [System.Text.Encoding]::GetEncoding(1252)
$fs = New-Object System.IO.FileStream($Jawe,[System.IO.FileMode]::Open,[System.IO.FileAccess]::Read,[System.IO.FileShare]::ReadWrite)
$sr = New-Object System.IO.StreamReader($fs,$enc)
$lines = $sr.ReadToEnd() -split "`r?`n"; $sr.Close(); $fs.Close()
$header = $lines[0].Split(';')
function Idx([string]$n){ for($i=0;$i -lt $header.Count;$i++){ if($header[$i].Trim() -eq $n){return $i} }; throw "Spalte '$n' fehlt." }
$iNr=Idx 'DZ_Nr'; $iName=Idx 'DZ_Name'; $iLand=Idx 'Land_Code'; $iKl=Idx 'Str_Kl'; $iSnr=Idx 'Str_Nr'
$iKm=Idx 'Betriebs_km'; $iWN=Idx 'Koor_WGS84_N'; $iWE=Idx 'Koor_WGS84_E'; $iAst=Idx 'Abschnitt_Ast'

$st=New-Object System.Collections.Generic.List[object]
for($r=1;$r -lt $lines.Count;$r++){
    if([string]::IsNullOrWhiteSpace($lines[$r])){continue}
    $c=$lines[$r].Split(';')
    if($c[$iKl].Trim() -ne 'A' -or $c[$iSnr].Trim() -ne '3'){continue}
    $lat=$c[$iWN].Trim() -replace ',','.'; $lon=$c[$iWE].Trim() -replace ',','.'
    if($lat -eq '' -or $lon -eq ''){continue}
    $ast=$c[$iAst].Trim()
    $st.Add([pscustomobject]@{
        Zst=$c[$iNr].Trim(); Name=$c[$iName].Trim(); Land=$c[$iLand].Trim()
        Lat=[double]::Parse($lat,$ci); Lon=[double]::Parse($lon,$ci); Km=$c[$iKm].Trim()
        Von=if($ast.Length -ge 16){$ast.Substring(0,8)}else{''}
        Nach=if($ast.Length -ge 16){$ast.Substring(8,8)}else{''}
    })
}
Write-Host ("A3-Zaehlstellen: {0}" -f $st.Count)

# Stationen entlang der Strecke ordnen (Nearest-Neighbor ab Nord-West) ---------
function Dist($a,$b){ $dy=$a.Lat-$b.Lat; $dx=($a.Lon-$b.Lon)*0.64; return $dy*$dy+$dx*$dx }
$pool=[System.Collections.Generic.List[object]]::new($st)
$cur=$pool | Sort-Object Lat -Descending | Select-Object -First 1
$ordered=New-Object System.Collections.Generic.List[object]
[void]$pool.Remove($cur); $ordered.Add($cur)
while($pool.Count -gt 0){
    $best=$null;$bd=[double]::MaxValue
    foreach($p in $pool){ $d=Dist $cur $p; if($d -lt $bd){$bd=$d;$best=$p} }
    [void]$pool.Remove($best); $ordered.Add($best); $cur=$best
}

# Globale Achse NW -> SO fuer die Richtungsbestimmung
$nw=$ordered[0]; $se=$ordered[$ordered.Count-1]
$axLat=$se.Lat-$nw.Lat; $axLon=$se.Lon-$nw.Lon

# --- 2) OSM-Geometrie laden --------------------------------------------------
Write-Host "Lese OSM-Geometrie ..."
$osmObj = Get-Content $Osm -Raw | ConvertFrom-Json
$ways = @($osmObj.elements | Where-Object { $_.type -eq 'way' -and $_.geometry })
Write-Host ("OSM-Wege (Fahrbahnen): {0}" -f $ways.Count)

# --- 3) JS-Daten bauen -------------------------------------------------------
# Stationen
$sbS=New-Object System.Text.StringBuilder
foreach($s in $ordered){
    $nm=$s.Name -replace '\\','\\' -replace "'","\'"
    [void]$sbS.AppendLine(("  {{zst:'{0}',name:'{1}',land:'{2}',lat:{3},lon:{4},km:'{5}',von:'{6}',nach:'{7}'}}," -f `
        $s.Zst,$nm,$s.Land,$s.Lat.ToString($ci),$s.Lon.ToString($ci),$s.Km,$s.Von,$s.Nach))
}
$staJs=$sbS.ToString().TrimEnd("`r","`n",",")

# Fahrbahnen: d = Richtung (0 = Sued-Ost, 1 = Nord-West), g = [[lat,lon],...]
$sbW=New-Object System.Text.StringBuilder
foreach($w in $ways){
    $g=$w.geometry
    if($g.Count -lt 2){continue}
    # A3 in Luxemburg ausblenden (eigene A3, geografisch getrennt von der BAB A3)
    $mid=$g[[int]($g.Count/2)]
    if($mid.lat -ge 49.30 -and $mid.lat -le 49.80 -and $mid.lon -ge 5.50 -and $mid.lon -le 6.60){ continue }
    $dLat=$g[$g.Count-1].lat - $g[0].lat
    $dLon=$g[$g.Count-1].lon - $g[0].lon
    $dot = $dLat*$axLat + $dLon*$axLon
    $dir = if($dot -ge 0){0}else{1}
    [void]$sbW.Append('{d:'); [void]$sbW.Append($dir); [void]$sbW.Append(',g:[')
    $first=$true
    foreach($pt in $g){
        if(-not $first){[void]$sbW.Append(',')}
        $first=$false
        [void]$sbW.Append('[')
        [void]$sbW.Append([math]::Round($pt.lat,5).ToString($ci))
        [void]$sbW.Append(',')
        [void]$sbW.Append([math]::Round($pt.lon,5).ToString($ci))
        [void]$sbW.Append(']')
    }
    [void]$sbW.AppendLine(']},')
}
$wayJs=$sbW.ToString().TrimEnd("`r","`n",",")

# --- 4) HTML schreiben -------------------------------------------------------
$html=@"
<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>BAB A3 - Zaehlstellen, Abschnitte & Fahrtrichtungen</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<style>
  html,body{margin:0;height:100%;font-family:'Segoe UI',Arial,Helvetica,sans-serif}
  #map{position:absolute;top:0;bottom:0;left:0;right:0}
  /* Umgebung nur leicht ausgrauen (entsaettigen), Helligkeit bleibt */
  .leaflet-tile{filter:grayscale(0.7) brightness(1.02)}
  .legend{background:rgba(255,255,255,.93);color:#222;padding:10px 13px;border-radius:8px;
          box-shadow:0 2px 10px rgba(0,0,0,.25);line-height:1.6;font-size:13px}
  .legend b{font-size:14px}
  .legend small{color:#666}
  .sw{display:inline-block;width:16px;height:5px;vertical-align:middle;margin-right:3px;border-radius:3px}
  .dot{display:inline-block;width:11px;height:11px;border-radius:50%;background:#111;border:2px solid #fff;
       box-shadow:0 0 2px #000;vertical-align:middle;margin-right:6px}
  /* Schlichtes helles Hover-Tooltip fuer Knotendetails */
  .leaflet-tooltip.nk-tip{background:rgba(255,255,255,.97);color:#222;border:1px solid rgba(0,0,0,.18);
          border-radius:8px;box-shadow:0 3px 14px rgba(0,0,0,.25);padding:8px 10px;font-size:12.5px;line-height:1.5;white-space:nowrap}
  .leaflet-tooltip.nk-tip b{color:#000}
  .leaflet-tooltip.nk-tip:before{display:none}
</style>
</head>
<body>
<div id="map"></div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const S = [
$staJs
];
const W = [
$wayJs
];

const map = L.map('map',{preferCanvas:true});
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
  {maxZoom:19,attribution:'&copy; OpenStreetMap-Mitwirkende'}).addTo(map);

// Farbpalette: [Richtung][Abschnitts-Paritaet]
// Richtung 0 = Sued-Ost (Passau): Blau ; Richtung 1 = Nord-West (Oberhausen): Rot
const COL = [ ['#0d47a1','#5e9cea'], ['#b71c1c','#f0825a'] ];

// naechstgelegene Zaehlstelle (entlang der Strecke) -> Abschnitts-Index
function nearestIdx(lat,lon){
  let bi=0,bd=Infinity;
  for(let i=0;i<S.length;i++){ const dy=lat-S[i].lat, dx=(lon-S[i].lon)*0.64; const d=dy*dy+dx*dx; if(d<bd){bd=d;bi=i;} }
  return bi;
}
function nkTip(s){
  return '<b>Knoten &middot; Zst '+s.zst+'</b> &mdash; '+s.name+
         '<br><b>Abschnitt_Ast (HW):</b> '+s.von+s.nach+
         '<br>Von-Netzknoten: <b>'+s.von+'</b> &nbsp; Nach-Netzknoten: <b>'+s.nach+'</b>'+
         '<br>Land: '+s.land+' &middot; Betriebs-km: '+s.km;
}

// Wege in Runs gleicher (Richtung, Abschnitts-Paritaet) zerlegen
const runs=[], all=[];
W.forEach(w=>{
  const g=w.g, dir=w.d;
  if(g.length<2) return;
  const par=g.map(p=> nearestIdx(p[0],p[1])%2 );
  let s=0;
  for(let i=1;i<g.length;i++){
    if(par[i]!==par[i-1]){ runs.push({dir:dir,par:par[i-1],pts:g.slice(s,i+1)}); s=i; }
  }
  runs.push({dir:dir,par:par[g.length-1],pts:g.slice(s)});
  for(const p of g) all.push(p);
});
runs.forEach(r=>{ const m=r.pts[(r.pts.length/2)|0]; r.si=nearestIdx(m[0],m[1]); });

// Strecke nur leicht hervorheben: dezente weisse Kontur unter dem farbigen Kern
// Pass 1: weisse Kontur -> hebt die Trasse leicht vom ausgegrauten Hintergrund ab
runs.forEach(r=> L.polyline(r.pts,{color:'#ffffff',weight:6,opacity:0.55,
  lineCap:'round',lineJoin:'round',interactive:false}).addTo(map));
// Pass 2: farbiger Kern + Hover-Tooltip mit Knotendetails
runs.forEach(r=>{
  L.polyline(r.pts,{color:COL[r.dir][r.par],weight:3.5,opacity:0.95,
    lineCap:'round',lineJoin:'round'}).addTo(map)
   .bindTooltip(nkTip(S[r.si]),{sticky:true,className:'nk-tip'});
});

// Zaehlstellen als Punkte - Knotendetails beim Hovern
S.forEach(s=>{
  L.circleMarker([s.lat,s.lon],{radius:6,color:'#fff',weight:2,fillColor:'#111',
    fillOpacity:1}).addTo(map)
   .bindTooltip(nkTip(s),{direction:'top',offset:[0,-3],className:'nk-tip'});
});

map.fitBounds(all,{padding:[25,25]});

const legend=L.control({position:'bottomright'});
legend.onAdd=function(){
  const d=L.DomUtil.create('div','legend');
  d.innerHTML='<b>BAB A3 &ndash; Richtungsfahrbahnen</b><br>'+
    '<span class="sw" style="background:#0d47a1"></span><span class="sw" style="background:#5e9cea"></span>Richtung S&uuml;d-Ost (Passau)<br>'+
    '<span class="sw" style="background:#b71c1c"></span><span class="sw" style="background:#f0825a"></span>Richtung Nord-West (Oberhausen)<br>'+
    '<span class="dot"></span>Zaehlstelle ('+S.length+')<br>'+
    '<small>Helligkeitswechsel = Abschnitte &middot; Hover = Knotendetails</small>';
  return d;
};
legend.addTo(map);
</script>
</body>
</html>
"@
[System.IO.File]::WriteAllText($OutFile,$html,(New-Object System.Text.UTF8Encoding($false)))
Write-Host ("Karte geschrieben: {0}" -f $OutFile)
