function MapaRadar() {
  return (
    <iframe
      src="https://www.rainviewer.com/map.html?loc=-16.6933,-49.2373,15&oFa=1&oC=1&oU=1&oCS=1&oF=1&oAP=0&c=1&o=83&lm=0&layer=radar&sm=1&sn=1"
      style={{ width: '100%', height: '100%', minHeight: '460px', border: 'none', borderRadius: '10px' }}
      title="Radar Meteorológico"
      allowFullScreen
    />
  );
}

export default MapaRadar;
