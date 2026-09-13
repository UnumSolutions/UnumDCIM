export class ApiError extends Error {
  constructor(message:string, public readonly status:number) {
    super(message);
    this.name = 'ApiError';
  }
}

export async function api<T>(service:string,path:string,role:string,body?:unknown):Promise<T>{
  const response=await fetch(`/api/${service}/${path}`,{method:body===undefined?'GET':'POST',headers:{'Content-Type':'application/json','X-Demo-Role':role},body:body===undefined?undefined:JSON.stringify(body)});
  const content=await response.json().catch(()=>({error:'Module unavailable'}));
  if(!response.ok)throw new ApiError(content.error||'Request failed',response.status);
  return content;
}
