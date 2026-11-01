import { createClient } from '@supabase/supabase-js';
const url=import.meta.env.VITE_SUPABASE_URL, key=import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY;
const app=document.getElementById('app');
if(!url||!key) throw new Error('Configure VITE_SUPABASE_URL and VITE_SUPABASE_PUBLISHABLE_KEY');
const supabase=createClient(url,key);
const escapeHtml=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function render(){
 const {data:{user},error}=await supabase.auth.getUser();
 const path=location.pathname;
 if(error||!user){
   if(path==='/dashboard') history.replaceState(null,'','/login');
   app.innerHTML='<h1>Global Career Architecture AI</h1><h2>Sign in or create an account</h2><form id="auth"><input type="email" name="email" placeholder="Email" required/><input type="password" name="password" placeholder="Password" minlength="8" required/><button name="action" value="signin">Sign in</button><button name="action" value="signup">Sign up</button></form><p id="status" role="status"></p>';
   app.querySelector('form').addEventListener('click',e=>{if(e.target.name==='action')app.querySelector('form').dataset.action=e.target.value});
   app.querySelector('form').addEventListener('submit',async e=>{e.preventDefault();const f=e.currentTarget;const email=f.elements.namedItem("email").value,password=f.elements.namedItem("password").value;const op=f.dataset.action==='signup'?'signUp':'signInWithPassword';const {error}=await supabase.auth[op]({email,password});if(error){app.querySelector('#status').textContent=error.message;return}if(op==='signUp'){app.querySelector('#status').textContent='Account created. Check your email for a confirmation link, then sign in.';return}history.replaceState(null,'','/dashboard');await render()});
   return;
 }
 if(path!=='/dashboard')history.replaceState(null,'','/dashboard');
 const {data:resumes,error:dbError}=await supabase.from('resumes').select('id,title,created_at').order('created_at',{ascending:false});
 app.innerHTML='<h1>Private dashboard</h1><p>Signed in: '+escapeHtml(user.email||'')+'</p><button id="signout">Sign out</button><form id="save"><input name="title" maxlength="200" required placeholder="Resume title"/><button>Save resume</button></form><p id="status" role="status"></p><ul>'+(resumes||[]).map(x=>'<li>'+escapeHtml(x.title)+'</li>').join('')+'</ul>';
 if(dbError)app.querySelector('#status').textContent='Could not load resumes';
 app.querySelector('#signout').onclick=async()=>{await supabase.auth.signOut();history.replaceState(null,'','/login');await render()};
 app.querySelector('#save').onsubmit=async e=>{e.preventDefault();const title=e.currentTarget.elements.namedItem("title").value;const {error}=await supabase.from('resumes').insert({title,content:{}});if(error){app.querySelector('#status').textContent='Unable to save resume';return}await render()};
}
supabase.auth.onAuthStateChange(()=>setTimeout(render,0));render();
