/* Run inside the authorized inews container. Read-only, explicit content fields only. */
const {DatabaseSync}=require('node:sqlite');
const dbPath=process.env.INEWS_DB_PATH || process.env.SINGLETITLE_DB || (process.env.INEWS_DATA_DIR || '/app/data')+'/inews.sqlite3';
const db=new DatabaseSync(dbPath,{readOnly:true});
try {
 const days=7,limit=2000,cutoff=Date.now()-days*86400000;
 const rows=db.prepare(`SELECT id,guid,url,title,title_zh,title_zh_profile,domain,publisher,published_at,first_seen_at,lang,cluster_id,relevance,genre FROM articles WHERE relevant=1 AND hidden_at IS NULL AND (published_at>=? OR first_seen_at>=?) ORDER BY first_seen_at DESC,id DESC LIMIT ?`).all(cutoff,cutoff,limit+1);
 process.stdout.write(JSON.stringify({schema:'inews-research-signals-v1',exported_at:new Date().toISOString(),window_days:days,truncated:rows.length>limit,scope:'bounded recent relevant, non-hidden article metadata; not full text or full history',articles:rows.slice(0,limit)})+'\n');
} finally {db.close();}
