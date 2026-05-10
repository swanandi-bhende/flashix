const fs=require('fs');
const p='../artifacts/build-info';
if(!fs.existsSync(p)){ console.error('artifacts/build-info not found at',p); process.exit(2); }
const files=fs.readdirSync(p).filter(f=>f.endsWith('.json'));
if(files.length===0){ console.error('no build-info JSON files'); process.exit(2); }
const bi=require(p+'/'+files[0]);
fs.mkdirSync('verification',{recursive:true});
fs.writeFileSync('verification/hardhat-compiler-input.json', JSON.stringify(bi.input,null,2));
console.log('wrote', 'verification/hardhat-compiler-input.json', 'from', files[0]);
