import type {Item, PageGeometry, Rect} from './api';

export function initialPlacement(item:Item, page:PageGeometry):Rect|null {
  if(item.placement)return item.placement;
  if(!item.has_image||!item.image_aspect)return null;
  const b=item.bounds;
  const ratio=item.image_aspect*page.height/page.width;
  const width=Math.min(b.width, b.height*ratio, 100/page.width);
  const height=width/ratio;
  return {x:b.x+(b.width-width)/2,y:b.y+(b.height-height)/2,width,height};
}

export function moveRect(rect:Rect, dx:number, dy:number, bounds:Rect):Rect {
  return {...rect,x:Math.max(bounds.x,Math.min(bounds.x+bounds.width-rect.width,rect.x+dx)),
    y:Math.max(bounds.y,Math.min(bounds.y+bounds.height-rect.height,rect.y+dy))};
}

export function resizeRect(rect:Rect, factor:number, bounds:Rect, page:PageGeometry):Rect {
  const max=Math.min((bounds.x+bounds.width-rect.x)/rect.width,(bounds.y+bounds.height-rect.y)/rect.height);
  const min=Math.max(5.1/(rect.width*page.width),5.1/(rect.height*page.height));
  const scale=Math.min(max,Math.max(min,factor));
  return {...rect,width:rect.width*scale,height:rect.height*scale};
}

export function isSafe(rect:Rect, bounds:Rect, page:PageGeometry):boolean {
  const e=0.000001;
  return rect.width*page.width>=5 && rect.height*page.height>=5
    && rect.x>=bounds.x-e && rect.y>=bounds.y-e
    && rect.x+rect.width<=bounds.x+bounds.width+e && rect.y+rect.height<=bounds.y+bounds.height+e
    && !page.text.some(w=>rect.x<w.x+w.width && rect.x+rect.width>w.x && rect.y<w.y+w.height && rect.y+rect.height>w.y);
}
