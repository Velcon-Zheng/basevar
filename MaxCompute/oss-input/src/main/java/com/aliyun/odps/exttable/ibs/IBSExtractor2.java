package com.aliyun.odps.exttable.ibs;

import com.aliyun.odps.Column;
import com.aliyun.odps.OdpsType;
import com.aliyun.odps.data.ArrayRecord;
import com.aliyun.odps.data.Record;
import com.aliyun.odps.io.InputStreamSet;
import com.aliyun.odps.io.SourceInputStream;
import com.aliyun.odps.udf.DataAttributes;
import com.aliyun.odps.udf.ExecutionContext;
import com.aliyun.odps.udf.Extractor;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.util.Date;
import java.util.HashMap;
import java.util.Map;
import java.util.Random;
import java.util.zip.GZIPInputStream;

/**
 * Created by tianli on 2017/8/7.
 */
public class IBSExtractor2 extends Extractor {

  private InputStreamSet inputs;
  private ArrayRecord record;

  private boolean isFirstRead = true;
  private int posIdx = -1;
  private int sampleIdx = -1;
  private String[] cols;
  private int majorCount = 0, minorCount = 0;
  private BufferedReader br = null;
  private Map<String, Integer> chrStartPosMap = new HashMap<String, Integer>(22);
  private boolean covMode = false;

  public void setup(ExecutionContext executionContext, InputStreamSet inputStreamSet, DataAttributes dataAttributes) {
    this.inputs = inputStreamSet;
    record = new ArrayRecord(getColumns());
    initChrStartPos(dataAttributes.getValueByKey("line.count"));
    String mode = dataAttributes.getValueByKey("mode");
    if (mode.equalsIgnoreCase("cov")) {
      covMode = true;
    }
  }

  private void initChrStartPos(String param) {
    Map<String, Integer> tmp = new HashMap<String, Integer>();
    for (String s : param.split("\n")) {
      String[] pair = s.split(" ");
      tmp.put(pair[0], Integer.valueOf(pair[1]));
    }
    int val = 0;
    for (int i = 1; i <= 22; i++) {
      chrStartPosMap.put("chr" + i, val);
      val += tmp.get("chr" + i + ".merge.mat.tsv.gz");
    }
  }

  private Column[] getColumns() {
    Column[] columns = new Column[3];
    columns[0] = new Column("sample_idx", OdpsType.BIGINT);
    columns[1] = new Column("pos_idx", OdpsType.BIGINT);
    columns[2] = new Column("val", OdpsType.DOUBLE);
    return columns;
  }

  public Record extract() throws IOException {
    String val;
    val = getNextVal();
    if (val == null) {
      return null;
    }

    record.setBigint("sample_idx", Long.valueOf(sampleIdx));
    record.setBigint("pos_idx", Long.valueOf(posIdx));
    record.setDouble("val", Double.valueOf(val));

    return record;
  }

  private String getNextVal() throws IOException {
    String val;
    do {
      ++sampleIdx;
      if (cols == null || sampleIdx == 0) {
        cols = getNextLine();
        if (cols == null) {
          return null;
        }
      }
      if (sampleIdx + 4 == cols.length) {
        sampleIdx = -1;
        if (covMode) {
          return String.valueOf(1.0 * minorCount / (minorCount + majorCount));
        }
        val = "N";
        continue;
      }
      String tmpVal = cols[sampleIdx+4];
      if (!covMode || tmpVal.equals("N")) {
        val = tmpVal;
        continue;
      } else {
        if (cols[2].equals(tmpVal)) {
          majorCount++;
          val = "0";
        } else if (cols[3].equals(tmpVal)) {
          minorCount++;
          val = "1";
        } else {
          minorCount=1;
          majorCount=1;
          return tmpVal;
        }
      }
    } while (val.equalsIgnoreCase("N"));
    return val;
  }

  private String[] getNextLine() throws IOException {
    String[] items;
    if (isFirstRead) {
      isFirstRead = false;
      br = getNextReader();
    }
    while (br != null) {
      String line;
      line = br.readLine();
      if (line == null) {
        br.close();
        br = getNextReader();
        continue;
      }
      items = line.split("\t");
      ++posIdx;
      sampleIdx = 0;
      minorCount = 0;
      majorCount = 0;
      if (items[2].equalsIgnoreCase(items[3])) {
        continue;
      }
      return items;
    }
    return null;
  }

  private BufferedReader getNextReader() throws IOException {
    String fileName;
    SourceInputStream sourceInputStream;

    do {
      sourceInputStream = inputs.next();
      if (sourceInputStream == null) {
        return null;
      }

      fileName = sourceInputStream.getFileName();
      System.err.println(fileName);
    } while (!fileName.endsWith(".af"));

    posIdx = chrStartPosMap.get(getChrName(fileName));
    BufferedReader br = new BufferedReader(
        new InputStreamReader(new AvailableInputStream(sourceInputStream)));
    return br;
  }

  private String getChrName(String fileName) {
    String[] pathParts = fileName.split("/");
    String[] tokens = pathParts[pathParts.length - 1].split("\\.");
    for (String token : tokens) {
      if (token.startsWith("chr")) {
        System.out.println("Chr name: " + token);
        return token;
      }
    }
    throw new RuntimeException("No chr name found");
  }

  public void close() {

  }

}
