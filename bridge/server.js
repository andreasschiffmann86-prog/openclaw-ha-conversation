const http = require('http');
const GW_WS = 'ws://127.0.0.1:18789';
const GW_TOKEN = 'fe4baf3ee27c1f97dae0358d64772d56c9416718c6cb0a10';
const PORT = parseInt(process.env.PORT || '18790');

let gw=null, gwReady=false;
const pending=new Map(), chatCbs=new Map();
let seq=0;
function uid(){return 'b'+(++seq)+'-'+Date.now();}

function gwConnect(){
  if(gw&&gw.readyState<2)return;
  gw=new WebSocket(GW_WS,{headers:{'Origin':'http://127.0.0.1:18789'}});
  gwReady=false;
  gw.addEventListener('message',function(ev){
    var m; try{m=JSON.parse(ev.data);}catch(e){return;}

    if(m.type==='event'&&m.event==='connect.challenge'){
      var id=uid();
      pending.set(id,{
        resolve:function(){
          gwReady=true;
          console.log('[bridge] connected, subscribing sessions...');
          // sessions.subscribe damit wir alle chat events empfangen
          gwReq('sessions.subscribe',{}).then(function(){
            console.log('[bridge] sessions subscribed - ready');
          }).catch(function(e){
            console.error('[bridge] subscribe failed:', e.message);
          });
        },
        reject:function(e){console.error('[bridge] auth fail:',e.message);}
      });
      gw.send(JSON.stringify({type:'req',id:id,method:'connect',params:{
        minProtocol:3,maxProtocol:3,
        client:{id:'openclaw-control-ui',version:'1.0.0',platform:'node',mode:'webchat'},
        role:'operator',
        scopes:['operator.admin','operator.read','operator.write','operator.approvals','operator.pairing'],
        caps:['tool-events'],
        auth:{token:GW_TOKEN},
        userAgent:'openclaw-ha-bridge/2.1',
        locale:'de'
      }}));
      return;
    }

    if(m.type==='res'){
      var p=pending.get(m.id);
      if(p){pending.delete(m.id); m.ok?p.resolve(m.payload):p.reject(new Error(m.error&&m.error.message||'err'));}
      return;
    }

    if(m.type==='event'&&m.event==='chat'){
      var d=m.payload; if(!d)return;
      var _sk=d.sessionKey; var cb=chatCbs.get(_sk)||chatCbs.get(_sk.replace("agent:main:","")); if(!cb)return;
      if(d.state==='final'||d.state==='aborted'){
        chatCbs.delete(d.sessionKey);
        gwReq("chat.history",{sessionKey:_sk,limit:5}).then(function(hist){
          var msgs=Array.isArray(hist&&hist.messages)?hist.messages:[];
          var txt='';
          for(var i=msgs.length-1;i>=0;i--){
            var m2=msgs[i];
            if(m2&&m2.role==='assistant'){
              var c='';
              if(Array.isArray(m2.content)){
                c=m2.content.filter(function(x){return x&&x.type==='text';}).map(function(x){return x.text;}).join('');
              } else {
                c=m2.text||m2.content||'';
              }
              if(c&&!/^NO_REPLY\s*$/.test(c.trim())){txt=c;break;}
            }
          }
          console.log('[bridge] response:', txt.slice(0,50));
          cb.resolve({response:txt,conversation_id:d.sessionKey});
        }).catch(function(){cb.resolve({response:'',conversation_id:d.sessionKey});});
      } else if(d.state==='error'){
        chatCbs.delete(d.sessionKey);
        cb.reject(new Error(d.errorMessage||'chat error'));
      }
    }
  });

  gw.addEventListener('close',function(){gwReady=false;console.log('[bridge] disconnected, reconnect...');setTimeout(gwConnect,3000);});
  gw.addEventListener('error',function(){});
}

function gwReq(method,params){
  return new Promise(function(resolve,reject){
    if(!gw||gw.readyState!==1){reject(new Error('not connected'));return;}
    var id=uid();
    pending.set(id,{resolve:resolve,reject:reject});
    gw.send(JSON.stringify({type:'req',id:id,method:method,params:params}));
    setTimeout(function(){if(pending.has(id)){pending.delete(id);reject(new Error('timeout'));}},30000);
  });
}

function sendAndWait(message,sessionKey,ms){
  return new Promise(function(resolve,reject){
    var timer=setTimeout(function(){chatCbs.delete(sessionKey);reject(new Error('response timeout'));},ms);
    chatCbs.set(sessionKey,{
      resolve:function(v){clearTimeout(timer);resolve(v);},
      reject:function(e){clearTimeout(timer);reject(e);}
    });
    gwReq('chat.send',{sessionKey:sessionKey,message:message,deliver:false,idempotencyKey:uid()}).catch(function(e){
      chatCbs.delete(sessionKey);clearTimeout(timer);reject(e);
    });
  });
}

var server=http.createServer(function(req,res){
  res.setHeader('Access-Control-Allow-Origin','*');
  res.setHeader('Access-Control-Allow-Methods','GET,POST,OPTIONS');
  res.setHeader('Access-Control-Allow-Headers','Content-Type,Authorization');
  if(req.method==='OPTIONS'){res.writeHead(204);res.end();return;}
  if(req.method==='GET'&&req.url==='/health'){
    res.writeHead(200,{'Content-Type':'application/json'});
    res.end(JSON.stringify({ok:true,gateway:gwReady,version:'2.1.0'}));
    return;
  }
  if(req.method!=='POST'||req.url!=='/conversation'){res.writeHead(404);res.end(JSON.stringify({error:'not found'}));return;}
  var body='';
  req.on('data',function(c){body+=c;});
  req.on('end',function(){
    var payload;
    try{payload=JSON.parse(body);}catch(e){res.writeHead(400);res.end(JSON.stringify({error:'invalid json'}));return;}
    var message=payload.message;
    var sessionKey=payload.conversation_id||('ha-'+Date.now());
    var ms=(payload.timeout||60)*1000;
    if(!message){res.writeHead(400);res.end(JSON.stringify({error:'message required'}));return;}
    if(!gwReady){res.writeHead(503);res.end(JSON.stringify({error:'gateway not ready'}));return;}
    console.log('[bridge] sending to session:', sessionKey, '-', message.slice(0,50));
    sendAndWait(message,sessionKey,ms).then(function(result){
      res.writeHead(200,{'Content-Type':'application/json'});
      res.end(JSON.stringify(result));
    }).catch(function(e){
      console.error('[bridge] error:', e.message);
      res.writeHead(500);res.end(JSON.stringify({error:e.message}));
    });
  });
});

gwConnect();
server.listen(PORT,'0.0.0.0',function(){console.log('[bridge] v2.1 on :'+PORT);});
