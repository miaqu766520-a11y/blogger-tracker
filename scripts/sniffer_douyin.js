// 抖音用户页作品列表嗅探器：挂钩 fetch+XHR，把 aweme/post 响应存进 window.__caps
// 用法：打开用户页 → 等稳定 → 注入本文件 → SPA 跳走再 history.back() → 读 window.__caps
window.__caps=[];
(function(){
  function map(d){
    return {n:(d.aweme_list||[]).length,
      data:(d.aweme_list||[]).map(function(v){
        return {id:v.aweme_id,t:(v.desc||"").slice(0,80),ct:v.create_time,
          digg:v.statistics&&v.statistics.digg_count,
          comm:v.statistics&&v.statistics.comment_count,
          share:v.statistics&&v.statistics.share_count,
          coll:v.statistics&&v.statistics.collect_count};
      }),
      mc:d.max_cursor,hm:d.has_more};
  }
  var O=window.fetch;
  window.fetch=function(){
    var u=arguments[0]&&arguments[0].url||arguments[0];
    return O.apply(this,arguments).then(function(r){
      try{
        if(String(u).indexOf("aweme/post")>-1){
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
        if(String(xhr.__u).indexOf("aweme/post")>-1){
          var d=JSON.parse(xhr.responseText);
          window.__caps.push({src:"xhr",d:map(d)});
        }
      }catch(e){}
    });
    return XS.apply(this,arguments);
  };
})();
"sniffer-ok"