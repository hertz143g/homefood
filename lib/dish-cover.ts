// One visible grapheme preserves joined emoji (for example 👩‍🍳) and skin tones.
export function singleEmoji(value:string):string|null {
  const segments=[...new Intl.Segmenter('ru',{granularity:'grapheme'}).segment(value.trim())];
  if(segments.length!==1)return null;
  const symbol=segments[0].segment;
  return /\p{Extended_Pictographic}|\p{Regional_Indicator}|\u20e3/u.test(symbol)?symbol:null;
}
export async function photoPreview(file:File):Promise<string>{
  if(!file.type.startsWith('image/'))throw new Error('Выберите изображение.');
  if(file.size>20*1024*1024)throw new Error('Выберите фото меньше 20 МБ.');
  const url=URL.createObjectURL(file);
  try{
    const image=new Image();image.src=url;
    try{await image.decode()}catch{throw new Error('Не удалось открыть фото. Попробуйте JPEG, PNG или WebP.')}
    const scale=Math.min(1,1400/Math.max(image.naturalWidth,image.naturalHeight));
    const canvas=document.createElement('canvas');canvas.width=Math.max(1,Math.round(image.naturalWidth*scale));canvas.height=Math.max(1,Math.round(image.naturalHeight*scale));
    const context=canvas.getContext('2d');if(!context)throw new Error('Не удалось обработать фото.');
    context.fillStyle='#ffffff';context.fillRect(0,0,canvas.width,canvas.height);context.drawImage(image,0,0,canvas.width,canvas.height);
    return canvas.toDataURL('image/jpeg',.84);
  }finally{URL.revokeObjectURL(url)}
}
