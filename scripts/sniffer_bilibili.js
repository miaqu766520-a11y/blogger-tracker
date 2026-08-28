// B站空间页作品列表嗅探器(备用路线):挂钩 fetch+XHR,把 arc/search 响应存进 window.__caps
// 主路线是「网络日志取签名 URL → 页内重取」,本文件用于签名失效等兜底场景:
// 注入后点击空间页内其他 Tab(如「动态」)再点回「投稿」,触发 arc/search 重发
window.__caps=[];
(function(){
  function pick(v){
    return {id:v.bvid,t:(v.title||"").slice(0,80),ct:v.created,
      play:v.play,comm:v.comment,len:v.length,pic:v.pic};
  }
  function map(d){
    var l=((d||{}).data||{}).list||{};
    return {n:(l.vlist||[]).length,data:(l.vlist||[]).map(pick)};
  }
  var O=window.fetch;
  window.fetch=function(){
    var u=arguments[0]&&arguments[0].url||arguments[0];
    return O.apply(this,arguments).then(function(r){
      try{
        if(String(u).indexOf("arc/search")>-1){
          r.clone().json().then(function(d){window.__caps.push({src:"fetch",d:map(d)})}).catch(function(){});
        }
      }catch(e){}
      return r;
    });
  };
  var XO=XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open=function(m,u){this.__u=u;return XO.apply(this,arguments);};
  var XS=XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.send=function(){
    var xhr=this;
    this.addEventListener("load",function(){
      try{
        if(String(xhr.__u).indexOf("arc/search")>-1){
          var d=JSON.parse(xhr.responseText);
          window.__caps.push({src:"xhr",d:map(d)});
        }
      }catch(e){}
    });
    return XS.apply(this,arguments);
  };
})();
"sniffer-ok"