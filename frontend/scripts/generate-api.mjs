import openapiTS, {astToString} from 'openapi-typescript';
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
const source = new URL('../../contracts/openapi.yaml',import.meta.url);
const text = await readFile(source,'utf8');
const output = '// Schema digest: '+createHash('sha256').update(text).digest('hex')+'\n'+astToString(await openapiTS(JSON.parse(text)));
const file = new URL('../src/api/generated.ts',import.meta.url);
if(process.argv.includes('--check')) {if(await readFile(file,'utf8')!==output)throw Error('API schema drift: run generate:api');}else await writeFile(file,output);
