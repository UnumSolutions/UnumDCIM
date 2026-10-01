export type AuthConfig = {mode:'demo'} | {
  mode:'oidc';issuer:string;client_id:string;redirect_uri:string;post_logout_redirect_uri:string;
  scope:string;acr_values:string;google_provider:string;
};

export function validateAuthConfig(value:unknown,origin:string):AuthConfig {
  if(!value || typeof value!=='object') throw new Error('Sign-in configuration is unavailable.');
  const config = value as Record<string,unknown>;
  if(config.mode==='demo') return {mode:'demo'};
  if(config.mode!=='oidc') throw new Error('An explicit authentication mode is required.');
  const fields = ['issuer','client_id','redirect_uri','post_logout_redirect_uri','scope','acr_values','google_provider'];
  if(fields.some(field=>typeof config[field]!=='string' || !(config[field] as string).trim())) {
    throw new Error('Sign-in configuration is incomplete.');
  }
  const issuer = new URL(config.issuer as string);
  const redirect = new URL(config.redirect_uri as string);
  const logout = new URL(config.post_logout_redirect_uri as string);
  if(new URL(origin).protocol!=='https:' || issuer.protocol!=='https:' || issuer.username || issuer.password || issuer.search || issuer.hash
    || redirect.origin!==origin || logout.origin!==origin || redirect.pathname!=='/auth/callback'
    || logout.pathname===redirect.pathname || [redirect,logout].some(url=>url.search || url.hash || url.username || url.password)) {
    throw new Error('Sign-in requires HTTPS and callbacks on this application origin.');
  }
  if(config.client_id!=='unum-web' || config.acr_values!=='urn:unum:acr:staff-mfa'
    || (config.scope as string).split(/\s+/).sort().join(' ')!=='email openid profile unum.api'
    || !/^[A-Za-z0-9_.-]+$/.test(config.google_provider as string)) {
    throw new Error('Sign-in configuration does not meet the application identity policy.');
  }
  return config as AuthConfig;
}
